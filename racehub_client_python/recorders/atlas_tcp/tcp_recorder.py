import asyncio
import struct
import math
import logging
from racehub_client_python.recorders.atlas_tcp.client import TCPRecorderClient
from racehub_client_python.recorders.atlas_tcp.data_types import (
    TriggerSource,
)
from racehub_client_python.recorders.atlas_tcp.configuration import (
    generate_configuration,
)

from racehub_client_python.recorders.atlas_tcp.parameters import (
    generate_tcp_parameters,
    CONFIGURATION_IDENTIFIER_REF,
)

from racehub_client_python.recorders.atlas_tcp.time_utilities import (
    TimeUtilities,
    NanoSeconds,
)

logger = logging.getLogger(__name__)


class TCPRecorder:
    def __init__(self):
        self.tcp_parameters = []
        self.tcp_packet_size = 0

        self.run_all_clients()

    def create_configuration(self):
        configuration_version = 1
        application_group_name = "RaceHub"
        frequency_in_hz = 5.0
        conversion_name = "Simple1to1"

        groups, packet_parameters, packet_size = generate_tcp_parameters(
            conversion_name,
            application_group_name,
            frequency_in_hz,
        )

        # Generate config & send it
        ok = generate_configuration(
            CONFIGURATION_IDENTIFIER_REF,
            configuration_version,
            conversion_name,
            groups,
        )
        if not ok:
            logger.error("Generate Configuration failed!")
            return {}, 0

        return packet_parameters, packet_size

    async def send_configuration(self, client: TCPRecorderClient):
        # Send configuration identifier
        ok = await client.send_configuration_identifier(CONFIGURATION_IDENTIFIER_REF)
        if not ok:
            logger.error(
                f"[Client {client.client_id}] Sending configuration failed! Will attempt reconnect."
            )
            return False
        return True

    async def run_data_loop(self, client: TCPRecorderClient):
        packet_parameters = self.tcp_parameters
        packet_size = self.tcp_packet_size

        frequency_in_hz = 5.0

        # Start time in whole seconds
        start_time_in_s = math.floor(TimeUtilities.get_now_since_midnight_in_seconds())

        # Data loop
        next_data_time_in_s = float(start_time_in_s)
        interval_in_ns = TimeUtilities.interval_in_nanoseconds(frequency_in_hz)
        offset_in_ns = NanoSeconds(0)

        data_buffer = bytearray(packet_size)

        logger.info(
            f"[Client {client.client_id}] Initialized data loop with {len(packet_parameters)} parameters, "
            f"packet size {packet_size} bytes."
        )

        last_telem_lap_number = None

        while True:
            now = TimeUtilities.get_now_since_midnight_in_seconds()
            while next_data_time_in_s < now:
                if not client.is_connected:
                    # If we've lost connection mid-loop, bail out so we can reconnect
                    return

                telemetry_data = self.get_latest_telemetry_data(client.client_id)

                lap_number = telemetry_data.get("lap_number", 0)

                if last_telem_lap_number != lap_number:

                    ok = await client.send_lap(
                        now,
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
                    else:
                        logger.info(
                            f"[Client {client.client_id}] Sent lap {lap_number} at {now}."
                        )

                    last_telem_lap_number = lap_number

                # We'll compute a wave value for each wave param
                for i in range(len(packet_parameters)):
                    param_name = packet_parameters[i]["name"]
                    offset_bytes = packet_parameters[i]["target_byte_offset"]
                    val = telemetry_data.get(param_name, 0.0)

                    # Pack as double
                    struct.pack_into("<d", data_buffer, offset_bytes, val)

                # ok_data = await client.send_data(next_data_time_in_s, data_buffer)
                ok_data = await client.send_data(now, data_buffer)
                if not ok_data:
                    logger.error(
                        f"[Client {client.client_id}] Failed to send data. Will attempt reconnect."
                    )
                    return

                offset_in_ns = NanoSeconds(offset_in_ns.value + interval_in_ns)
                next_data_time_in_s = start_time_in_s + offset_in_ns.seconds

            # Sleep to reduce CPU usage
            await asyncio.sleep(0.1)

    async def run_single_client(self, host: str, port: int, client_id: int):
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

            ok = await self.send_configuration(client)
            if not ok:
                logger.error(
                    f"[Client {client.client_id}] Sending configuration failed! Will attempt reconnect."
                )
                break

            try:
                await self.run_data_loop(client)
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

    def run_all_clients(self):
        """
        Orchestrator that spins up multiple clients (e.g., 20).
        Each client connects to a different port from 4560 to 4579.
        """
        host = "127.0.0.1"
        port_start = 4560
        port_count = 22  # total clients
        tasks = []

        packet_parameters, packet_size = self.create_configuration()

        self.tcp_parameters = packet_parameters
        self.tcp_packet_size = packet_size

        for i in range(port_count):
            port = port_start + i
            # We'll name the tasks for debugging
            client_task = asyncio.create_task(self.run_single_client(host, port, i))
            tasks.append(client_task)

        # Run all tasks concurrently. They will each handle their own reconnect logic.
        asyncio.gather(*tasks)

    def get_latest_telemetry_data(self, client_id: int):
        raise NotImplementedError("get_latest_telemetry_data not implemented")
