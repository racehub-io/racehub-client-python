import argparse
import asyncio
import subprocess
import websockets
import json
from websockets.exceptions import ConnectionClosedOK
import logging
from logging.handlers import RotatingFileHandler
import os
import requests
import socket
import sys
import platform
import signal
import threading
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from contextlib import asynccontextmanager

from racehub_client_python import __version__, config
from racehub_client_python.utils import get_recorder_metadata, save_recorder_metadata
from racehub_client_python.grpc_service import serve_grpc

# Globals
tray_icon = None
current_state = "disconnected"
worker_processes = []
shutdown_event = threading.Event()

# Logging setup
worker_processes = []


def get_log_file_path():
    if platform.system() == "Windows":
        local_app_data = os.getenv("LOCALAPPDATA")
        log_dir = os.path.join(local_app_data, "RaceHub", "logs")
    elif platform.system() == "Darwin":
        home_dir = os.path.expanduser("~")
        log_dir = os.path.join(home_dir, "Library", "Logs", "RaceHub")
    else:
        home_dir = os.path.expanduser("~")
        log_dir = os.path.join(home_dir, ".racehub", "logs")

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "racehub_client.log")
    return log_file


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_file_path = get_log_file_path()

# Configure rotating file handler
log_handler = RotatingFileHandler(
    log_file_path, maxBytes=5 * 1024 * 1024, backupCount=2
)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(log_handler)

# Remove previous basicConfig to avoid duplicate logs
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set of connected clients
connected_clients = set()

# Store client authentication details
client_auth = {}

allowed_origins = [None, "http://localhost:3000", "http://127.0.0.1:3000"]
allowed_origins.extend(
    origin.strip()
    for origin in os.environ.get("RACEHUB_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
)

recorders = {}
buffers = {}
recorder_files = {}

parser_queue = asyncio.Queue()
post_processing_queue = asyncio.Queue()

recorder_metadata = get_recorder_metadata()
save_recorder_metadata(recorder_metadata)

tray_icon = None
current_state = "disconnected"


# Function to get the icon path
def get_icon_path(icon_name):
    if getattr(sys, "frozen", False):
        # Running in a bundle
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(base_path, icon_name)
    return icon_path


# Function to create an icon image based on the state
def create_image(state="disconnected"):
    # Load the base icon
    icon_path = get_icon_path("icon.ico")
    if os.path.exists(icon_path):
        base_image = Image.open(icon_path).convert("RGBA")
    else:
        # Create a default image if icon not found
        base_image = Image.new("RGBA", (64, 64), "white")

    # Create an overlay for the status circle
    overlay = Image.new("RGBA", base_image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Determine the color
    color_map = {"disconnected": "red", "connected": "yellow", "running": "green"}
    color = color_map.get(state, "blue")  # Default to blue if state is unknown

    # Draw the circle on the lower right corner
    circle_radius = 10
    circle_diameter = circle_radius * 2
    position = (
        base_image.size[0] - circle_diameter - 5,
        base_image.size[1] - circle_diameter - 5,
        base_image.size[0] - 5,
        base_image.size[1] - 5,
    )
    draw.ellipse(position, fill=color)

    # Composite the overlay onto the base image
    combined_image = Image.alpha_composite(base_image, overlay)

    return combined_image


# Function to update the tray icon based on the state
def update_tray_icon():
    global tray_icon, current_state
    if tray_icon:
        tray_icon.icon = create_image(current_state)
        tray_icon.visible = True


# Function to open the log file
def open_log_file(icon, item):
    """
    Open the log file in a text editor.
    """
    log_file_path = get_log_file_path()
    try:
        if platform.system() == "Windows":
            os.startfile(log_file_path)  # Windows
        elif platform.system() == "Darwin":
            subprocess.run(["open", log_file_path], check=True)  # macOS
        else:
            subprocess.run(["xdg-open", log_file_path], check=True)  # Linux
    except Exception as e:
        logger.error(f"Failed to open log file: {e}", exc_info=True)


# Function to update the current state and tray icon
def update_state(state):
    global current_state
    current_state = state
    update_tray_icon()


# Function to quit the app
def quit_app(icon, item):
    """
    Trigger application shutdown from the tray icon.
    """
    logger.info("Tray icon triggered quit. Stopping application...")
    icon.stop()  # Stop the tray icon
    shutdown_event.set()  # Notify the main thread to shut down


# Taskbar setup function
def setup_taskbar():
    global tray_icon
    tray_icon = Icon(
        "RaceHubClient",
        create_image(current_state),
        menu=Menu(MenuItem("Open Logs", open_log_file), MenuItem("Exit", quit_app)),
    )
    tray_icon.run()


# Function to send the initial message to the websocket client
async def send_initial_message(websocket):
    major, minor, patch = map(int, __version__.split("."))
    await websocket.send(
        json.dumps(
            {
                "action": "CLIENT_INITIALISED",
                "payload": {
                    "versionMajor": major,
                    "versionMinor": minor,
                    "versionPatch": patch,
                    "platform": f"{platform.system()} {platform.release()}",
                    "hostname": socket.gethostname(),
                },
            }
        )
    )


# Message handler function
async def handle_message(websocket, message):
    data = json.loads(message)
    action = data.get("action")
    payload = data.get("payload")

    if action == "WEB_RESPONSE_AUTH_TOKEN":
        # Save the uid and auth_token
        userId = payload.get("uid")
        token = payload.get("token")

        client_auth[websocket] = {
            "uid": userId,
            "token": token,
        }

        async def log_to_firestore(userId, token):
            # Log the machine details to Firestore
            url = os.environ.get("RACEHUB_MACHINE_USAGE_URL")
            if not url:
                return
            data = {
                "userId": userId,
                "machineName": socket.gethostname(),
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.post(url, data=json.dumps(data), headers=headers)

            if response.status_code == 200:
                await send_message(
                    "CLIENT_RESPONSE_MACHINE_LOGGED",
                    {
                        "status": "success",
                        "machineName": socket.gethostname(),
                        "message": "",
                    },
                )
            else:
                await send_message(
                    "CLIENT_RESPONSE_MACHINE_LOGGED",
                    {
                        "status": "error",
                        "machineName": socket.gethostname(),
                        "message": response.text,
                    },
                )

        if userId and token:
            asyncio.create_task(log_to_firestore(userId, token))

    elif action == "START_RECORDING":
        logger.info(f"Starting recorder with payload: {payload}")
        update_state("running")
        asyncio.create_task(start_recorder(payload))
    elif action == "STOP_RECORDING":
        logger.info("Stopping recorder")
        update_state("connected")
        asyncio.create_task(stop_recorder(payload))
    elif action == "WEB_REQUEST_KILL_CLIENT":
        # Stop all active recorders and exit the application
        await asyncio.gather(
            *(stop_recorder({"recorderId": recorderId}) for recorderId in recorders)
        )
        sys.exit(0)
    elif action == "WEB_REQUEST_GET_DATA":
        # Retrieve data from the buffer
        recorderId = payload.get("recorderId")
        car_index = int(payload.get("carIndex"), 0)
        parameter = payload.get("parameter")
        start_time = payload.get("startTime", None)
        end_time = payload.get("endTime", None)

        if recorderId not in buffers:
            return

        data = buffers[recorderId]

        if start_time:
            start_time = float(start_time)
            data = [d for d in data if start_time <= d["timestamp"][car_index]]

        if end_time:
            end_time = float(end_time)
            data = [d for d in data if d["timestamp"][car_index] <= end_time]

        data = [
            {
                "timestamp": d["timestamp"][car_index],
                "session_time": d["session_time"][car_index],
                "distance": d["distance"][car_index],
                "value": d[parameter][car_index],
            }
            for d in data
        ]

        await send_message(
            "CLIENT_RESPONSE_GET_DATA",
            {
                "recorderId": recorderId,
                "carIndex": car_index,
                "parameter": parameter,
                "startTime": start_time,
                "endTime": end_time,
                "data": data,
            },
        )
    else:
        logger.warning(f"Unknown action: {action}")


# Function to start the recorder
# Function to start the recorder
async def start_recorder(payload):
    await send_message(
        "CLIENT_RESPONSE_RECORDER_INITIALISING",
        {"recorderId": payload.get("recorderId")},
    )
    payload["workerType"] = "recorder"
    payload_bytes = json.dumps(payload).encode("utf-8")

    # Determine the correct executable based on the platform
    if getattr(sys, "frozen", False):
        worker_executable = (
            os.path.join(os.path.dirname(sys.executable), "RaceHubWorker.exe")
            if platform.system() == "Windows"
            else os.path.join(os.path.dirname(sys.executable), "RaceHubWorker")
        )
    else:
        worker_executable = (
            "./dist/RaceHubWorker.exe"
            if platform.system() == "Windows"
            else "./dist/RaceHubWorker"
        )

    # Prepare creationflags to suppress console window on Windows
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW

    # Start the worker process
    try:
        process = await asyncio.create_subprocess_exec(
            worker_executable,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,  # Suppress console window on Windows
        )

        # Track the worker process in the global list
        worker_processes.append(process)

        # Send the payload to the worker process
        process.stdin.write(payload_bytes)
        await process.stdin.drain()
        process.stdin.close()

        # Read the output of the worker process
        async def read_stream(stream, callback):
            while True:
                line = await stream.readline()
                if line:
                    # logger.debug(f"Worker output: {line.decode().strip()}")
                    await callback(line)
                else:
                    break

        # Start reading the streams in parallel
        await asyncio.gather(
            read_stream(process.stdout, handle_worker_message),
            read_stream(process.stderr, handle_worker_message),
        )

        return process

    except Exception as e:
        logger.error(f"Failed to start recorder process: {e}", exc_info=True)
        raise


# Function to stop the recorder
async def stop_recorder(payload):
    recorderId = payload.get("recorderId")
    stop_filename = f"STOP_{recorderId}"
    os.makedirs(config["recordings_dir"], exist_ok=True)
    stop_file_path = os.path.join(config["recordings_dir"], stop_filename)
    open(stop_file_path, "w").close()


# Function to parse a file
async def parse_file(payload):
    logger.info(f"File parsing has started {payload}")
    payload["workerType"] = "parser"
    payload_bytes = json.dumps(payload).encode("utf-8")

    # Determine the correct executable based on the platform
    if getattr(sys, "frozen", False):
        worker_executable = (
            os.path.join(os.path.dirname(sys.executable), "RaceHubWorker.exe")
            if platform.system() == "Windows"
            else os.path.join(os.path.dirname(sys.executable), "RaceHubWorker")
        )
    else:
        worker_executable = (
            "./dist/RaceHubWorker.exe"
            if platform.system() == "Windows"
            else "./dist/RaceHubWorker"
        )

    # Prepare creationflags to suppress console window on Windows
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW

    # Start the worker process
    process = await asyncio.create_subprocess_exec(
        worker_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,  # Suppress console window
    )

    # Store the process
    worker_processes.append(process)

    # Send the payload to the worker process
    process.stdin.write(payload_bytes)
    await process.stdin.drain()
    process.stdin.close()

    # Read the output of the worker process
    async def read_stream(stream, callback):
        while True:
            line = await stream.readline()
            if line:
                # logger.debug(f"Worker output: {line.decode().strip()}")
                await callback(line)
            else:
                break

    await asyncio.gather(
        read_stream(process.stdout, handle_worker_message),
        read_stream(process.stderr, handle_worker_message),
    )


# Function to post-process a file
async def post_process_file(payload):
    payload["workerType"] = "post_processor"
    payload_bytes = json.dumps(payload).encode("utf-8")

    # Determine the correct executable based on the platform
    if getattr(sys, "frozen", False):
        worker_executable = (
            os.path.join(os.path.dirname(sys.executable), "RaceHubWorker.exe")
            if platform.system() == "Windows"
            else os.path.join(os.path.dirname(sys.executable), "RaceHubWorker")
        )
    else:
        worker_executable = (
            "./dist/RaceHubWorker.exe"
            if platform.system() == "Windows"
            else "./dist/RaceHubWorker"
        )

    # Prepare creationflags to suppress console window on Windows
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NO_WINDOW

    # Start the worker process
    process = await asyncio.create_subprocess_exec(
        worker_executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,  # Suppress console window
    )

    # Store the process
    worker_processes.append(process)

    # Send the payload to the worker process
    process.stdin.write(payload_bytes)
    await process.stdin.drain()
    process.stdin.close()

    # Read the output of the worker process
    async def read_stream(stream, callback):
        while True:
            line = await stream.readline()
            if line:
                # logger.debug(f"Worker output: {line.decode().strip()}")
                await callback(line)
            else:
                break

    await asyncio.gather(
        read_stream(process.stdout, handle_worker_message),
        read_stream(process.stderr, handle_worker_message),
    )


# Function to send a message to all connected clients
async def send_message(action, payload):
    message = json.dumps({"action": action, "payload": payload})
    for client in connected_clients:
        await client.send(message)


# Function to handle messages from the worker
async def handle_worker_message(line):
    try:
        message = json.loads(line.decode())
    except json.JSONDecodeError:
        logger.error(f"Failed to decode message: {line}")
        return

    if not isinstance(message, dict):
        logger.error(f"Message is not a dict: {message}")
        return

    if not message.get("action") or not message.get("payload"):
        logger.error(f"Message missing action or payload: {message}")
        return

    action = message.get("action")
    payload = message.get("payload")

    # Handle worker error
    if action == "WORKER_ERROR":
        error_message = payload.get("message")
        logger.error(f"Worker Error: {error_message}")
        # Optionally, send this error message back to connected clients
        await send_message("CLIENT_WORKER_ERROR", {"message": error_message})
        return

    # Handle various actions
    if action == "WORKER_RESPONSE_RECORDER_STARTED":
        recorderId = payload.get("recorderId")
        recorders[recorderId] = payload
        buffers[recorderId] = []
        await send_message(
            "CLIENT_RESPONSE_RECORDER_STARTED", {"recorderId": recorderId}
        )
    elif action == "WORKER_RESPONSE_RECORDER_STOPPED":
        recorderId = payload.get("recorderId")
        if recorderId in recorders:
            del recorders[recorderId]
        if recorderId in buffers:
            del buffers[recorderId]
        if recorderId in recorder_files:
            del recorder_files[recorderId]
        await send_message(
            "CLIENT_RESPONSE_RECORDER_STOPPED", {"recorderId": recorderId}
        )
    elif action == "WORKER_RESPONSE_RECORDER_STATUS":
        await send_message("CLIENT_RESPONSE_RECORDER_STATUS", payload)
    elif action == "WORKER_RESPONSE_RECORDER_ARCHIVE_CREATED":
        archive_path = payload.get("archive_path")
        recorder_metadata[archive_path] = {
            "partitions": {},
            "all_partitions_parsed": False,
            "post_processed": False,
        }
        save_recorder_metadata(recorder_metadata)
        await send_message("CLIENT_RESPONSE_RECORDER_ARCHIVE_CREATED", payload)
    elif action == "WORKER_RESPONSE_RECORDER_PARTITION_CREATED":
        recorderId = payload.get("recorderId")
        archive_path = payload.get("archive_path")
        partition_path = payload.get("partition_path")
        recorder_files[recorderId] = {
            "archive_path": archive_path,
            "partition_path": partition_path,
        }

        partition_filename = os.path.basename(partition_path)
        recorder_metadata[archive_path]["partitions"][partition_filename] = {
            "parsed": False,
        }

        await send_message("CLIENT_RESPONSE_RECORDER_PARTITION_CREATED", payload)
    elif action == "WORKER_RESPONSE_RECORDER_PARTITION_CLOSED":
        await parser_queue.put(
            {
                "archive_path": payload.get("archive_path"),
                "partition_path": payload.get("partition_path"),
                "partition_number": payload.get("partition_number"),
            }
        )
        await send_message("CLIENT_RESPONSE_RECORDER_PARTITION_CLOSED", payload)
    elif action == "WORKER_RESPONSE_RECORDER_ARCHIVE_CLOSED":
        await send_message("CLIENT_RESPONSE_RECORDER_ARCHIVE_CLOSED", payload)
    elif action == "WORKER_RESPONSE_PARSER_STARTED":
        await send_message("CLIENT_RESPONSE_PARSER_STARTED", payload)
    elif action == "WORKER_RESPONSE_PARSER_FINISHED":
        archive_path = payload.get("archive_path")
        partition_number = int(payload.get("partition_number"))
        partition_filename = f"{partition_number:04d}.rhc"

        recorder_metadata[archive_path]["partitions"][partition_filename] = {
            "parsed": True,
        }

        # Check if all partitions have been parsed and if the archive is inactive
        archive_active = archive_path in (
            recorder["archive_path"] for recorder in recorder_files.values()
        )
        all_partitions_parsed = all(
            partition_details.get("parsed")
            for partition_details in recorder_metadata[archive_path][
                "partitions"
            ].values()
        )

        if all_partitions_parsed and not archive_active:
            recorder_metadata[archive_path]["all_partitions_parsed"] = True
            await post_processing_queue.put(archive_path)

        save_recorder_metadata(recorder_metadata)
        await send_message("CLIENT_RESPONSE_PARSER_FINISHED", payload)
    elif action == "WORKER_RESPONSE_PARSER_STATUS":
        await send_message("CLIENT_RESPONSE_PARSER_STATUS", payload)
    elif action == "WORKER_RESPONSE_PARSER_MESSAGE":
        await send_message("CLIENT_RESPONSE_PARSER_MESSAGE", payload)
    elif action == "WORKER_RESPONSE_PARSER_ERROR":
        await send_message("CLIENT_RESPONSE_PARSER_ERROR", payload)
    elif action == "WORKER_RESPONSE_POST_PROCESSOR_STARTED":
        await send_message("CLIENT_RESPONSE_POST_PROCESSOR_STARTED", payload)
    elif action == "WORKER_RESPONSE_POST_PROCESSOR_FINISHED":
        archive_path = payload.get("archive_path")
        recorder_metadata[archive_path]["post_processed"] = True
        save_recorder_metadata(recorder_metadata)
        await send_message("CLIENT_RESPONSE_POST_PROCESSOR_FINISHED", payload)
    elif action == "WORKER_RESPONSE_POST_PROCESSOR_STATUS":
        await send_message("CLIENT_RESPONSE_POST_PROCESSOR_STATUS", payload)
    elif action == "WORKER_RESPONSE_POST_PROCESSOR_MESSAGE":
        await send_message("CLIENT_RESPONSE_POST_PROCESSOR_MESSAGE", payload)
    elif action == "WORKER_RESPONSE_POST_PROCESSOR_ERROR":
        await send_message("CLIENT_RESPONSE_POST_PROCESSOR_ERROR", payload)
    elif action == "WORKER_RESPONSE_RECORDER_LIVE_DATA":
        recorderId = payload.get("recorderId")
        data = payload.get("data")
        await send_message(
            "CLIENT_RESPONSE_RECORDER_LIVE_DATA",
            {"recorderId": recorderId, "data": data},
        )
    elif action == "WORKER_RESPONSE_RECORDER_PROTO_MESSAGE":
        recorderId = payload.get("recorderId")
        messageType = payload.get("messageType")
        data = payload.get("data")
        await send_message(
            "CLIENT_RESPONSE_RECORDER_PROTO_MESSAGE",
            {"recorderId": recorderId, "messageType": messageType, "data": data},
        )
    else:
        logger.warning(f"Unknown worker action: {action}")


async def server(websocket, path):
    try:
        connected_clients.add(websocket)
        update_state("connected")
        logger.info(f"New client connected: {websocket.remote_address}")
        await send_initial_message(websocket)
        async for message in websocket:
            await handle_message(websocket, message)
    except ConnectionClosedOK:
        logger.info("Client disconnected gracefully.")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        connected_clients.discard(websocket)
        if not connected_clients:
            update_state("disconnected")
            logger.info("All clients disconnected.")


async def main_server_loop():
    try:
        logger.info("Initializing WebSocket server on ws://localhost:8082...")
        server_task = await websockets.serve(
            server, "localhost", 8082, origins=allowed_origins
        )
        logger.info("WebSocket server started. Awaiting connections...")

        # Start parser and postprocessing workers as independent tasks
        parser_task = asyncio.create_task(parser_worker_loop())
        postprocessor_task = asyncio.create_task(postprocessing_worker_loop())

        # Await server shutdown
        await server_task.wait_closed()

        # Cancel the worker tasks if server shuts down
        parser_task.cancel()
        postprocessor_task.cancel()

        # Optionally, wait for them to finish
        await asyncio.gather(parser_task, postprocessor_task, return_exceptions=True)
    except Exception as e:
        logger.error("Error in WebSocket server loop:", exc_info=True)


async def parser_worker_loop():
    # Populate the queue with partitions that need parsing
    for archive_path, archive_details in recorder_metadata.items():
        for partition_filename, partition_details in archive_details[
            "partitions"
        ].items():
            if not partition_details.get("parsed"):
                partition_path = os.path.join(archive_path, partition_filename)
                await parser_queue.put(
                    {
                        "archive_path": archive_path,
                        "partition_path": partition_path,
                        "partition_number": partition_filename.split(".")[0],
                    }
                )

    while True:
        queue_length = parser_queue.qsize()

        await send_message(
            "CLIENT_RESPONSE_PARSER_QUEUE_LENGTH", {"queueLength": queue_length}
        )

        partition_details = await parser_queue.get()

        if not partition_details:
            await asyncio.sleep(10)
            continue

        partition_path = partition_details.get("partition_path")

        if not os.path.exists(partition_path):
            logger.error(f"Couldnt find path for parser {partition_path}")

        if not os.path.exists(partition_path):
            await parser_queue.put(partition_details)
            await asyncio.sleep(1)
            continue

        if partition_path in [
            recorder["partition_path"] for recorder in recorder_files.values()
        ]:
            await parser_queue.put(partition_details)
            await asyncio.sleep(1)
            continue

        await parse_file(partition_details)


# Post-processing worker loop
async def postprocessing_worker_loop():
    # Populate the queue with archives that need post-processing
    for archive_path, archive_details in recorder_metadata.items():
        if archive_details.get("all_partitions_parsed") and not archive_details.get(
            "post_processed"
        ):
            await post_processing_queue.put(archive_path)

    while True:
        queue_length = post_processing_queue.qsize()

        await send_message(
            "CLIENT_RESPONSE_POSTPROCESSING_QUEUE_LENGTH",
            {"queueLength": queue_length},
        )

        archive_path = await post_processing_queue.get()

        if not archive_path:
            await asyncio.sleep(10)
            continue

        if not os.path.exists(archive_path):
            await post_processing_queue.put(archive_path)
            await asyncio.sleep(1)
            continue

        if archive_path in [
            recorder["archive_path"] for recorder in recorder_files.values()
        ]:
            await post_processing_queue.put(archive_path)
            await asyncio.sleep(1)
            continue

        await post_process_file({"archive_path": archive_path})


# Graceful Process Management
@asynccontextmanager
async def manage_process(*args, **kwargs):
    process = await asyncio.create_subprocess_exec(*args, **kwargs)
    worker_processes.append(process)
    try:
        yield process
    finally:
        logger.info(f"Terminating process {process.pid}")
        process.terminate()
        await process.wait()


def terminate_processes():
    logger.info("Terminating all worker processes...")
    for process in worker_processes:
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception as e:
            logger.error(f"Failed to terminate process {process.pid}: {e}")


async def shutdown():
    """
    Gracefully shut down tasks and worker processes.
    """
    logger.info("Shutdown initiated. Cleaning up...")

    # Terminate all worker processes
    for process in worker_processes:
        try:
            if platform.system() == "Windows":
                # Use taskkill for Windows
                logger.info(f"Terminating worker process {process.pid} on Windows")
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            else:
                # Use os.killpg for Unix-like systems
                logger.info(
                    f"Terminating worker process {process.pid} on Unix-like system"
                )
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception as e:
            logger.error(f"Failed to terminate worker process {process.pid}: {e}")

    # Stop the asyncio event loop
    logger.info("Stopping asyncio event loop.")
    loop = asyncio.get_event_loop()
    loop.stop()

    logger.info("Shutdown complete.")


# Main Functions
async def main_async():
    logger.debug("Starting main_async...")

    # Start the tray icon in a separate thread (existing code)
    tray_thread = threading.Thread(target=setup_taskbar, daemon=True)
    tray_thread.start()
    logger.info("Tray icon thread started.")

    # Create the WebSocket server task (existing code)
    server_task = asyncio.create_task(main_server_loop())

    # Create the gRPC server task (NEW)
    # You could choose a different port if you like
    grpc_task = asyncio.create_task(serve_grpc(port=50051))

    try:
        # Wait until the user triggers shutdown via tray icon or other means
        while not shutdown_event.is_set():
            await asyncio.sleep(0.1)

        logger.info("Shutdown event triggered. Cleaning up...")

        # Cancel the server tasks
        server_task.cancel()
        grpc_task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(server_task, grpc_task, return_exceptions=True)

        # Then do your normal shutdown routine
        await shutdown()

    except asyncio.CancelledError:
        logger.info("Main server tasks cancelled.")
    except Exception as e:
        logger.error("Unexpected error in main_async:", exc_info=True)
    finally:
        if tray_thread.is_alive():
            logger.debug("Waiting for tray thread to exit...")
            tray_thread.join()


def main():
    parser = argparse.ArgumentParser(description="Run the server.")
    parser.add_argument("-s", action="store_true", help="Run in staging mode.")
    global STAGING
    STAGING = parser.parse_args().s

    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.error("Unexpected error in main:", exc_info=True)


if __name__ == "__main__":
    main()
