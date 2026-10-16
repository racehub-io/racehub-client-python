from typing import Optional
import asyncio
import struct
import logging

from racehub_client_python.recorders.atlas_tcp.time_utilities import TimeUtilities

logger = logging.getLogger(__name__)


class TCPRecorderClient:
    MESSAGE_PROTOCOL_VERSION = 2

    class MessageType:
        CONFIG = 150
        DATA = 151
        LAP = 152

    def __init__(self, client_id: int, send_buffer_size=0):
        self.client_id = client_id
        self.send_buffer_size = send_buffer_size
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected = False

        self.lap_number = 1

    async def attempt_connect(
        self, host: str, port: int, retry_interval: float = 10.0, max_attempts: int = 0
    ) -> bool:
        """
        Repeatedly attempt to connect to the given host/port.
        :param retry_interval: seconds to wait between attempts
        :param max_attempts: how many attempts before giving up (0 => infinite)
        :return: True if connected, False if we gave up
        """
        attempt_count = 0
        while True:
            attempt_count += 1
            try:
                logger.info(
                    f"[Client {self.client_id}] Attempting to connect to {host}:{port} (attempt {attempt_count})"
                )
                self.reader, self.writer = await asyncio.open_connection(host, port)
                self.is_connected = True
                logger.info(f"[Client {self.client_id}] Connected to {host}:{port}")
                return True
            except (OSError, ConnectionError) as e:
                self.is_connected = False
                logger.warning(
                    f"[Client {self.client_id}] Connection attempt {attempt_count} failed: {e}"
                )
                if max_attempts > 0 and attempt_count >= max_attempts:
                    logger.error(
                        f"[Client {self.client_id}] Max connection attempts exceeded. Giving up."
                    )
                    return False
                else:
                    logger.info(
                        f"[Client {self.client_id}] Retrying in {retry_interval} seconds..."
                    )
                    await asyncio.sleep(retry_interval)

    async def send_configuration_identifier(
        self, configuration_identifier: str
    ) -> bool:
        if not self.is_connected or not self.writer:
            return False
        config_bytes = configuration_identifier.encode("ascii")
        timestamp = TimeUtilities.get_now_since_midnight_in_seconds()
        success = await self.send_header(
            self.MessageType.CONFIG, timestamp, len(config_bytes)
        )
        if not success:
            return False
        try:
            self.writer.write(config_bytes)
            await self.writer.drain()
            return True
        except (OSError, ConnectionError) as e:
            logger.error(
                f"[Client {self.client_id}] Failed to write configuration identifier: {e}"
            )
            self.is_connected = False
            return False

    async def send_data(self, timestamp: float, *buffers: bytes) -> bool:
        if not self.is_connected or not self.writer:
            return False
        total_size = sum(len(b) for b in buffers)
        success = await self.send_header(self.MessageType.DATA, timestamp, total_size)
        if not success:
            return False
        try:
            for b in buffers:
                self.writer.write(b)
            await self.writer.drain()
            return True
        except (OSError, ConnectionError) as e:
            logger.error(f"[Client {self.client_id}] Failed to write data: {e}")
            self.is_connected = False
            return False

    async def send_lap(
        self,
        timestamp: float,
        number: int,
        trigger_source: int,
        name: str,
        count_for_fastest_lap: bool,
    ) -> bool:
        if not self.is_connected or not self.writer:
            return False

        name_bytes = name.encode("ascii")
        # short => h, byte => B, int => i (for name length), bool => ?
        buffer = (
            struct.pack("<hB i", number, trigger_source, len(name_bytes))
            + name_bytes
            + struct.pack("<?", count_for_fastest_lap)
        )
        success = await self.send_header(self.MessageType.LAP, timestamp, len(buffer))
        if not success:
            return False
        try:
            self.writer.write(buffer)
            await self.writer.drain()
            return True
        except (OSError, ConnectionError) as e:
            logger.error(f"[Client {self.client_id}] Failed to write lap: {e}")
            self.is_connected = False
            return False

    async def send_header(
        self, message_type: int, timestamp: float, data_length: int
    ) -> bool:
        if not self.writer:
            return False
        # struct layout: <HH I d
        header = struct.pack(
            "<HH I d",
            message_type,
            self.MESSAGE_PROTOCOL_VERSION,
            data_length + struct.calcsize("<HH I d"),
            timestamp,
        )
        try:
            self.writer.write(header)
            await self.writer.drain()
            return True
        except (OSError, ConnectionError) as e:
            logger.error(f"[Client {self.client_id}] Failed to write header: {e}")
            self.is_connected = False
            return False

    def close(self):
        if self.writer:
            self.writer.close()
        self.is_connected = False
