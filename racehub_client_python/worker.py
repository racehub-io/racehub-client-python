import json
import sys
import asyncio
import selectors
import socket
import logging
import traceback

from racehub_client_python.recorders.f12022recorder import F12022Recorder
from racehub_client_python.recorders.f12023recorder import F12023Recorder
from racehub_client_python.recorders.f12024recorder import F12024Recorder
from racehub_client_python.recorders.iracingrecorder import iRacingRecorder
from racehub_client_python.workers.parser import parse_partition
from racehub_client_python.workers.postprocess import post_process_file

RECORDERS = {
    "F12022": F12022Recorder,
    "F12023": F12023Recorder,
    "F12024": F12024Recorder,
    "iRacing": iRacingRecorder,
}

def create_and_run_recorder(config):
    recorder_id = config.get("recorderId")
    recorderType = config.get("recorderType")
    inPort = config.get("inPort")
    outAddress = config.get("outAddress")
    outPort = config.get("outPort")
    forwardingEnabled = config.get("forwardingEnabled")

    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", inPort))

    recorder = RECORDERS.get(recorderType)

    # One protocol instance will be created to serve all client requests
    listen = loop.create_datagram_endpoint(
        lambda: recorder(
            recorder_id, recorderType, loop, outAddress, outPort, forwardingEnabled
        ),
        sock=sock,
    )
    transport, protocol = loop.run_until_complete(listen)

    protocol.start()  # Start the stop file check

    try:
        loop.run_forever()
    except Exception as e:
        logging.error(f"Caught exception: {e}")
    finally:
        protocol._stop_file_check_task.cancel()
        transport.close()
        loop.close()

def create_and_run_parser(config):
    try:
        parse_partition(config)
    except EOFError as e:
        # Handle EOFError
        error_message = f"EOFError during parsing: {e}"
        print(json.dumps({
            "action": "WORKER_ERROR",
            "payload": {"message": error_message}
        }))
        sys.exit(1)
    except Exception as e:
        # Send the exception details back to the client in JSON format
        error_message = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__))
        print(json.dumps({
            "action": "WORKER_ERROR",
            "payload": {"message": error_message}
        }))
        sys.exit(1)

def create_and_run_post_processor(config):
    try:
        post_process_file(config)
    except Exception as e:
        # Send the exception details back to the client in JSON format
        error_message = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__))
        print(json.dumps({
            "action": "WORKER_ERROR",
            "payload": {"message": error_message}
        }))
        sys.exit(1)

if __name__ == "__main__":
    try:
        config = json.loads(sys.stdin.read())
        worker_type = config.get("workerType")
        if worker_type == "recorder":
            create_and_run_recorder(config)
        elif worker_type == "parser":
            create_and_run_parser(config)
        elif worker_type == "post_processor":
            create_and_run_post_processor(config)
        else:
            print(json.dumps({
                "action": "WORKER_ERROR",
                "payload": {"message": f"Unknown worker type: {worker_type}"}
            }))
            sys.exit(1)

    except EOFError:
        print(json.dumps({
            "action": "WORKER_ERROR",
            "payload": {"message": "Input stream was closed unexpectedly (EOFError)."}
        }))
        sys.exit(1)

    except Exception as e:
        error_message = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__))
        print(json.dumps({
            "action": "WORKER_ERROR",
            "payload": {"message": error_message}
        }))
        sys.exit(1)