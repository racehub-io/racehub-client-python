import asyncio
import os
import json
import logging
import struct
import datetime as dt
import gzip
import sys

from racehub_client_python.constants import RECORDER_TYPES
from racehub_client_python import __version__, config
from racehub_client_python.workers.fileheader import FileHeader

logger = logging.getLogger(__name__)


class BaseRecorder(object):
    def __init__(
        self, recorder_id, recorderType, loop, outAddress, outPort, forwardingEnabled
    ):
        self.recorder_id = recorder_id
        self.recorderType = recorderType
        self.outAddress = outAddress
        self.outPort = outPort
        self.forwardingEnabled = forwardingEnabled
        self.is_running = True

        self.session_metadata = {}

        self.current_session_id = None

        self.loop = loop
        self._partition = 0
        self._message_count = 0
        self._last_heartbeat = 0

        self._archive_path = None
        self._archive_timestamp = None

        self._partition_path = None
        self._partition_gz_file = None

    def create_archive(self):
        now = dt.datetime.now()
        formatted_timestamp = now.strftime("%Y%m%d_%H%M%S")
        folder_name = f"{self.recorder_id}_{formatted_timestamp}"
        folder_path = os.path.join(config["recordings_dir"], folder_name)

        # check if folder exists
        if os.path.exists(folder_path):
            logging.error(f"Folder {folder_path} already exists")

        # create folder
        try:
            os.mkdir(folder_path)
        except OSError:
            logging.error(f"Creation of the directory {folder_path} failed")
        else:
            logging.info(f"Successfully created the directory {folder_path}")

        self._partition = 0
        self._archive_path = folder_path
        self._archive_timestamp = now

        self.send_message(
            "WORKER_RESPONSE_RECORDER_ARCHIVE_CREATED",
            {
                "recorderId": self.recorder_id,
                "archive_path": self._archive_path,
            },
        )

    def connection_made(self, transport):
        self.transport = transport
        self.send_message(
            "WORKER_RESPONSE_RECORDER_STARTED", {"recorderId": self.recorder_id}
        )

    def error_received(self, exc):
        pass

    #     self.send_message(
    #         "WORKER_RESPONSE_RECORDER_ERROR_RECEIVED",
    #         {"recorderId": self.recorder_id},
    #     )

    def connection_lost(self, exc):
        self.is_running = False
        if self._partition_gz_file:
            self.close_partition()
            self.close_archive()
        self.send_message(
            "WORKER_RESPONSE_RECORDER_STOPPED", {"recorderId": self.recorder_id}
        )

    async def check_for_stop_file(self, interval_seconds=1):
        """
        Check for the stop file periodically and stop if found.

        Args:
            interval_seconds (int): Interval between checks in seconds.
        """
        stop_filename = f"STOP_{self.recorder_id}"

        while self.is_running:
            stop_filepath = os.path.join(config["recordings_dir"], stop_filename)
            if os.path.exists(stop_filepath):
                logging.info("Stop file found, stopping...")
                self.is_running = False
                self.stop()

                # Delete the stop file
                try:
                    os.remove(stop_filepath)
                    logging.info("Stop file deleted.")
                except Exception as e:
                    logging.error(f"Error while deleting stop file: {e}")

                return

            await asyncio.sleep(interval_seconds)

    def start(self):
        self._stop_file_check_task = self.loop.create_task(self.check_for_stop_file())

    def stop(self):
        """
        Stop the UDPListener.
        """
        logging.info("Stopping...")
        self.is_running = False

        if self._partition_gz_file:
            self.close_partition()
            self.close_archive()
        self.loop.stop()  # Stop the event loop

        self.send_message(
            "WORKER_RESPONSE_RECORDER_STOPPED", {"recorderId": self.recorder_id}
        )

    def create_partition(self):
        """
        Create a new archive file.

        Args:
            m_packetFormat (int): Packet format.
        """
        logging.info("Creating archive...")

        self._partition += 1

        if self._partition_gz_file:
            self.close_partition()

        filepath = os.path.join(self._archive_path, f"{self._partition:04d}.rhc")
        self._partition_path = filepath

        self._partition_gz_file = gzip.open(filepath, "wb")

        major, minor, patch = map(int, __version__.split("."))

        header = FileHeader()
        header.rhc_version_major = major
        header.rhc_version_minor = minor
        header.rhc_version_patch = patch
        header.recorder_type = RECORDER_TYPES.get(self.recorderType, 0)
        header.recorder_name = self.recorder_id.encode("utf-8")
        header.partition = self._partition
        header.year = self._archive_timestamp.year
        header.month = self._archive_timestamp.month
        header.day = self._archive_timestamp.day
        header.hour = self._archive_timestamp.hour
        header.minute = self._archive_timestamp.minute
        header.second = self._archive_timestamp.second
        header.millisecond = self._archive_timestamp.microsecond // 1000

        headerBuffer = bytearray(header)
        mSize = struct.pack("H", len(headerBuffer))

        self._partition_gz_file.write(mSize)
        self._partition_gz_file.write(headerBuffer)

        self.send_message(
            "WORKER_RESPONSE_RECORDER_PARTITION_CREATED",
            {
                "recorderId": self.recorder_id,
                "archive_path": self._archive_path,
                "partition_path": self._partition_path,
                "partition_number": self._partition,
            },
        )

    def close_archive(self):
        self.send_message(
            "WORKER_RESPONSE_RECORDER_ARCHIVE_CLOSED",
            {
                "recorderId": self.recorder_id,
                "archive_path": self._archive_path,
            },
        )

        self._archive_path = None

    def close_partition(self):
        """
        Close the current archive partition.
        """
        if self._partition_gz_file:
            logging.info("Closing archive...")
            self._partition_gz_file.close()
            self._partition_gz_file = None

            self.send_message(
                "WORKER_RESPONSE_RECORDER_PARTITION_CLOSED",
                {
                    "recorderId": self.recorder_id,
                    "archive_path": self._archive_path,
                    "partition_path": self._partition_path,
                    "partition_number": self._partition,
                },
            )

        self._partition_path = None

        self.partition_metadata = {}

    def send_message(self, action, payload):
        """
        Send a message to the server through stdout
        """
        message = json.dumps({"action": action, "payload": payload})
        sys.stdout.write(f"{message}\n")
        sys.stdout.flush()

    def send_proto_message(self, message_type, proto_message):
        # proto_message_hex = proto_message.hex()

        action = "WORKER_RESPONSE_RECORDER_PROTO_MESSAGE"

        payload = {
            "recorderId": self.recorder_id,
            "messageType": message_type,
            "data": proto_message,
        }

        self.send_message(action, payload)

    def send_telem_message(self, telem_message):
        action = "WORKER_RESPONSE_RECORDER_LIVE_DATA"

        payload = {
            "recorderId": self.recorder_id,
            "data": telem_message,
        }

        self.send_message(action, payload)

    ## TCP Configuration
