import asyncio
import math
import random
import logging
import struct

from typing import List

from racehub_client_python.recorders.atlas_tcp.client import TCPRecorderClient
from racehub_client_python.recorders.atlas_tcp.configuration import (
    generate_configuration,
)
from racehub_client_python.recorders.atlas_tcp.data_types import (
    PacketFieldType,
    TriggerSource,
)
from racehub_client_python.recorders.atlas_tcp.time_utilities import (
    TimeUtilities,
    NanoSeconds,
)


###############################################################################
# Set up logging (similar to NLog)
###############################################################################
logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG level so we see more detailed logs
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TCPRecorderSample")


###############################################################################
# SAMPLE PROGRAM LOGIC
###############################################################################


def create_parameter_set(num_params: int) -> List[dict]:
    """
    Create a list of 'num_params' parameters.
    We'll have at least one special 'TimestampParam' for diagnosing delays.
    The rest will be some wave-like data.
    """
    params = []
    # Always add one special param for diagnosing timestamp
    params.append(
        {
            "name": "TimestampParam",
            "description": "Packet Send Time",
            "packet_field_type": PacketFieldType.DOUBLE,
            "min_value": 0,
            "max_value": 1000000,
            "format": "%.6f",
        }
    )

    wave_types = ["SineWave", "CosineWave", "RandomWave", "TanWave"]
    # We'll do (num_params - 1) wave params
    for i in range(num_params - 1):
        wave_name = wave_types[i % len(wave_types)]
        param_dict = {
            "name": f"{wave_name}{i}",
            "description": f"Sample {wave_name} {i}",
            "packet_field_type": PacketFieldType.DOUBLE,
            "min_value": -100,
            "max_value": 100,
            "format": "%.3f",
        }
        params.append(param_dict)
    return params


async def run_data_loop(client: TCPRecorderClient):
    """
    The main loop that sends data packets periodically, plus lap info.
    """
    # Configuration settings
    # configuration_identifier_ref = [f"SampleConfiguration_Client{client.client_id}"]
    configuration_identifier_ref = ["SampleConfiguration_Client"]
    configuration_version = 1
    # application_group_name = f"SampleParams_Client{client.client_id}"
    application_group_name = "SampleParams_Client"
    frequency_in_hz = 10.0  # 10 Hz for easier multi-client load

    # We'll create 100 total parameters for each client
    packet_parameters = create_parameter_set(100)

    # Generate config & send it
    packet_size = generate_configuration(
        configuration_identifier_ref,
        configuration_version,
        application_group_name,
        frequency_in_hz,
        packet_parameters,
    )
    if packet_size <= 0:
        logger.error(f"[Client {client.client_id}] Generate Configuration failed!")
        return  # Just return, we'll attempt reconnect again from outside

    # Send configuration identifier
    ok = await client.send_configuration_identifier(configuration_identifier_ref[0])
    if not ok:
        logger.error(
            f"[Client {client.client_id}] Sending configuration failed! Will attempt reconnect."
        )
        return

    # Start time in whole seconds
    start_time_in_s = math.floor(TimeUtilities.get_now_since_midnight_in_seconds())

    # Send first lap
    lap_number = 1
    ok = await client.send_lap(
        start_time_in_s,
        lap_number,
        TriggerSource.DEFAULT,
        f"Lap {lap_number}",
        True,
    )
    if not ok:
        logger.error(
            f"[Client {client.client_id}] Sending lap failed! Will attempt reconnect."
        )
        return

    lap_number += 1
    next_lap_time_in_s = start_time_in_s + 30.0  # shorter laps for demo

    # Data loop
    next_data_time_in_s = float(start_time_in_s)
    interval_in_ns = TimeUtilities.interval_in_nanoseconds(frequency_in_hz)
    offset_in_ns = NanoSeconds(0)

    angle_interval_in_rads = (2.0 * math.pi) / (5.0 * frequency_in_hz)
    angle_in_rads = 0.0

    data_buffer = bytearray(packet_size)

    # Track parameter offsets from generate_configuration()
    param_offsets = {}
    for p in packet_parameters:
        param_offsets[p["name"]] = p["target_byte_offset"]

    # We'll store wave values for each param. We'll randomize 'RandomWave'
    rand = random.Random(client.client_id)

    logger.info(
        f"[Client {client.client_id}] Initialized data loop with {len(packet_parameters)} parameters, "
        f"packet size {packet_size} bytes."
    )

    iteration_count = 0

    while True:
        now = TimeUtilities.get_now_since_midnight_in_seconds()
        while next_data_time_in_s < now:
            if not client.is_connected:
                # If we've lost connection mid-loop, bail out so we can reconnect
                return

            iteration_count += 1

            # For the special "TimestampParam", store the current 'now' time
            struct.pack_into("<d", data_buffer, param_offsets["TimestampParam"], now)

            # We'll compute a wave value for each wave param
            for i in range(1, len(packet_parameters)):
                param_name = packet_parameters[i]["name"]
                offset_bytes = param_offsets[param_name]
                # Identify wave type by name
                if "SineWave" in param_name:
                    val = math.sin(angle_in_rads + i / 50.0) * 50
                elif "CosineWave" in param_name:
                    val = math.cos(angle_in_rads + i / 50.0) * 50
                elif "TanWave" in param_name:
                    # be mindful that tan can blow up, but let's just do it anyway
                    val = math.tan(angle_in_rads + i / 50.0) * 10
                elif "RandomWave" in param_name:
                    val = (rand.random() - 0.5) * 100  # range ~ -50..50
                else:
                    val = 0.0  # fallback

                # Pack as double
                struct.pack_into("<d", data_buffer, offset_bytes, val)

            angle_in_rads += angle_interval_in_rads

            ok_data = await client.send_data(next_data_time_in_s, data_buffer)
            if not ok_data:
                logger.error(
                    f"[Client {client.client_id}] Failed to send data. Will attempt reconnect."
                )
                return

            # Optional: add a debug log every so many packets
            if iteration_count % 50 == 0:
                logger.debug(
                    f"[Client {client.client_id}] Sent packet #{iteration_count}, "
                    f"timestamp={next_data_time_in_s:.3f}"
                )

            offset_in_ns = NanoSeconds(offset_in_ns.value + interval_in_ns)
            next_data_time_in_s = start_time_in_s + offset_in_ns.seconds

            if next_lap_time_in_s < now:
                ok_lap = await client.send_lap(
                    next_lap_time_in_s,
                    lap_number,
                    TriggerSource.DEFAULT,
                    f"Lap {lap_number}",
                    True,
                )
                if not ok_lap:
                    logger.error(
                        f"[Client {client.client_id}] Failed to send lap. Will attempt reconnect."
                    )
                    return
                lap_number += 1
                next_lap_time_in_s += 30.0 + (-5.0 + rand.random() * 10.0)

        # Sleep to reduce CPU usage
        await asyncio.sleep(0.2 + rand.random() * 0.2)


async def run_single_client(host: str, port: int, client_id: int):
    """
    Single client logic. Tries to keep a connection, runs the data loop if connected.
    """
    client = TCPRecorderClient(client_id)
    while True:
        connected = await client.attempt_connect(
            host, port, retry_interval=10.0, max_attempts=0
        )
        if not connected:
            logger.error(
                f"[Client {client.client_id}] Could not connect after repeated attempts. Exiting."
            )
            break

        try:
            await run_data_loop(client)
        except asyncio.CancelledError:
            logger.info(
                f"[Client {client.client_id}] Cancelled run_data_loop. Exiting."
            )
            break
        except Exception as ex:
            logger.error(
                f"[Client {client.client_id}] run_data_loop exception: {ex}",
                exc_info=True,
            )

        logger.info(
            f"[Client {client.client_id}] Lost connection or error occurred. Will attempt to reconnect."
        )
        client.close()
        await asyncio.sleep(2.0)


async def run_all_clients():
    """
    Orchestrator that spins up multiple clients (e.g., 20).
    Each client connects to a different port from 4560 to 4579.
    """
    host = "127.0.0.1"
    port_start = 4560
    port_count = 20  # total clients
    tasks = []

    for i in range(port_count):
        port = port_start + i
        # We'll name the tasks for debugging
        client_task = asyncio.create_task(run_single_client(host, port, i))
        tasks.append(client_task)

    # Run all tasks concurrently. They will each handle their own reconnect logic.
    await asyncio.gather(*tasks)


def main():
    """
    If you want a synchronous entrypoint, we just run the event loop on run_all_clients().
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_all_clients())
    except KeyboardInterrupt:
        logger.info("User interrupted with CTRL+C. Exiting.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
