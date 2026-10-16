import ctypes
import gzip
import logging
import traceback
import os

# from racehub_client_python import config
from racehub_client_python.workers.websockets import send_message
from racehub_client_python.workers.fileheader import FileHeader

from racehub_client_python.workers.parsers.f12022 import F12022Parser
from racehub_client_python.workers.parsers.f12023 import F12023Parser
from racehub_client_python.workers.parsers.f12024 import F12024Parser
from racehub_client_python.workers.parsers.iracing import IRacingParser

PARSERS = {
    1: F12022Parser,
    2: F12023Parser,
    3: F12024Parser,
    4: IRacingParser,
}


def parse(partition_details):
    partition_path = partition_details["partition_path"]

    # Check if the file exists
    if not os.path.exists(partition_path):
        logging.error(f"Partition does not exist: {partition_path}")
        return

    with gzip.open(partition_path, "rb") as partition_file:
        # get the size of the file
        partition_file.seek(0, os.SEEK_END)
        partition_size = partition_file.tell()

        partition_file.seek(0, os.SEEK_SET)

        # if partition is empty, return
        if not partition_size:
            return

        # Read the file header
        if partition_size < (2 + ctypes.sizeof(FileHeader)):
            return

        partition_file.seek(2)
        partition_header_data = partition_file.read(ctypes.sizeof(FileHeader))
        partition_header = FileHeader.from_buffer_copy(partition_header_data)
        recorder_type = partition_header.recorder_type

    parser_class = PARSERS.get(recorder_type, None)

    parser = parser_class(partition_details)

    parser.parse()


def parse_partition(config):
    try:
        send_message(
            "WORKER_RESPONSE_PARSER_STARTED",
            {
                "archive_path": config.get("archive_path"),
                "partition_path": config.get("partition_path"),
                "partition_number": config.get("partition_number"),
            },
        )
        parse(config)
        send_message(
            "WORKER_RESPONSE_PARSER_FINISHED",
            {
                "archive_path": config.get("archive_path"),
                "partition_path": config.get("partition_path"),
                "partition_number": config.get("partition_number"),
            },
        )
    except EOFError as e:
        error_message = f"EOFError during parsing: {e}"
        send_message(
            "WORKER_ERROR",
            {"message": error_message}
        )
    except Exception as e:
        error_message = ''.join(traceback.format_exception(e.__class__, e, e.__traceback__))
        send_message(
            "WORKER_ERROR",
            {"message": error_message}
        )

