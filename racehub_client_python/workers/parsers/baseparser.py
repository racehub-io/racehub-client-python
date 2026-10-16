import gzip
import logging
import os

from racehub_client_python import config
from racehub_client_python.workers.fileheader import FileHeader


def get_output_filepath(recorder_name, file_timestamp, car_index, partition_number):
    output_dir = os.path.join(
        config["recordings_dir"],
        f"{recorder_name}_{file_timestamp.strftime('%Y%m%d_%H%M%S')}",
        f"{car_index}",
    )

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    return os.path.join(
        output_dir,
        f"{partition_number}.pq",
    )


class BaseParser:
    def __init__(self, partition_details):
        self.partition_details = partition_details
        self.partition_file = None
        self.header = None
        self.partition_size = 0

        self.open_partition()

        # get the size of the file
        self.partition_file.seek(0, os.SEEK_END)
        self.partition_size = self.partition_file.tell()

        self.partition_file.seek(0, os.SEEK_SET)

        # if partition is empty, return
        if not self.partition_size:
            logging.error(f"Partition is empty: {self.partition_details}")

        self.read_header()

    def open_partition(self):
        partition_path = self.partition_details["partition_path"]

        # Check if the file exists
        if not os.path.exists(partition_path):
            logging.error(f"Partition does not exist: {partition_path}")
            return

        self.partition_file = gzip.open(partition_path, "rb")

    def close_partition(self):
        if self.partition_file:
            self.partition_file.close()

    def read_header(self):
        # Read the file header
        length_data = self.partition_file.read(2)
        header_length = int.from_bytes(length_data, byteorder="little")
        partition_header_data = self.partition_file.read(header_length)
        self.header = FileHeader.from_buffer_copy(partition_header_data)

    def parse(self):
        logging.error("Not implemented")

    def __del__(self):
        self.close_partition()
