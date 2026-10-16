import datetime as dt
import json
import pyarrow as pa
import pyarrow.parquet as pq

from racehub_client_python.workers.parsers import BaseParser, get_output_filepath
from racehub_client_python.workers.websockets import send_message
import racehub_client_python.utils.iracing_message_pb2 as iRacingProto
import racehub_client_python.utils.racehub_pb2 as RaceHubMessage
from racehub_client_python.utils.protoconversions import PROTO_TO_PYARROW_MAP

NUM_CARS = 64


def get_schema(file_details={}, session_details={}, participant_details={}):
    car_fields = RaceHubMessage.Car.DESCRIPTOR.fields
    participant_fields = RaceHubMessage.Participant.DESCRIPTOR.fields
    session_info_fields = RaceHubMessage.Session.DESCRIPTOR.fields

    fields = [
        pa.field(field.name, PROTO_TO_PYARROW_MAP[field.type]) for field in car_fields
    ]

    fields += [
        pa.field(field.name, PROTO_TO_PYARROW_MAP[field.type])
        for field in participant_fields
    ]

    fields += [
        pa.field(field.name, PROTO_TO_PYARROW_MAP[field.type])
        for field in session_info_fields
    ]

    metadata = {
        **file_details,
        **session_details,
        **participant_details,
    }

    metadata = {
        b"racehub": json.dumps(
            {**file_details, **session_details, **participant_details}
        )
    }

    return pa.schema(fields, metadata=metadata)


class IRacingParser(BaseParser):
    def __init__(self, partition_details):
        BaseParser.__init__(self, partition_details)

    def parse(self):
        partition_path = self.partition_details["partition_path"]
        partition_number = self.partition_details["partition_number"]

        recorder_name = self.header.recorder_name.decode("utf-8").rstrip("\x00")
        partition_timestamp = dt.datetime(
            year=self.header.year,
            month=self.header.month,
            day=self.header.day,
            hour=self.header.hour,
            minute=self.header.minute,
            second=self.header.second,
            microsecond=self.header.millisecond * 1000,
        )

        file_progress = 0

        writers = {
            car: {
                "buffer": [],
                "partition": 0,
            }
            for car in range(NUM_CARS)
        }

        partition_header_dict = self.header.to_dict()

        session_details = {
            "session_timestamp": dt.datetime.now().timestamp(),
            "session_id": "",
            "series": "",
            "event_name": "",
            "session_name": "",
            "track_name": "",
            "track_length": 0,
            "air_temp": 0,
            "track_temp": 0,
        }

        participant_details = [
            {
                "player_name": "Unknown",
                "driver_name": "Unknown",
                "driver_abbreviation": "DRV",
                "driver_number": 0,
                "driver_nationality": "",
                "team_name": "",
                "laps": [],
                "tyres": [],
            }
            for _ in range(NUM_CARS)
        ]

        packet = None
        next_progress_threshold = 0

        while True:
            length_data = self.partition_file.read(2)
            if not length_data:
                break

            packet_length = int.from_bytes(length_data, byteorder="little")
            packet_bytes = self.partition_file.read(packet_length)

            packet = iRacingProto.iRacingMessage()
            packet.ParseFromString(packet_bytes)

            for idx, car in enumerate(packet.cars):
                row = {
                    field.name: getattr(car, field.name)
                    for field in car.DESCRIPTOR.fields
                }
                participant = packet.participants[idx]
                session_info = packet.session

                row.update(
                    {
                        field.name: getattr(participant, field.name)
                        for field in participant.DESCRIPTOR.fields
                    }
                )
                row.update(
                    {
                        field.name: getattr(session_info, field.name)
                        for field in session_info.DESCRIPTOR.fields
                    }
                )

                writers[idx]["buffer"].append(row)

            file_progress += (packet_length / self.partition_size) * 100
            if file_progress >= next_progress_threshold:
                send_message(
                    "WORKER_RESPONSE_PARSER_STATUS",
                    {
                        "filepath": partition_path,
                        "progress": file_progress,
                        "trackName": session_details.get("track_name", ""),
                        "sessionType": session_details.get("session_name", ""),
                    },
                )
                next_progress_threshold += 1

        if not packet:
            return

        session_details.update(
            {
                "session_id": packet.session.session_id,
                "series": packet.session.series,
                "event_name": packet.session.event_name,
                "track_name": packet.session.track_name,
                "track_length": packet.session.track_length,
                "air_temp": packet.session.air_temperature,
                "track_temp": packet.session.track_temperature,
            }
        )

        for idx, participant in enumerate(packet.participants):
            participant_details[idx].update(
                {
                    "player_name": participant.driver_name,
                    "driver_name": participant.driver_name,
                    "driver_abbreviation": participant.abbreviation,
                    "driver_number": participant.car_number,
                    "team_name": participant.team_name,
                }
            )

        for car_index, writer in writers.items():
            if writer["buffer"]:
                output_filepath = get_output_filepath(
                    recorder_name, partition_timestamp, car_index, partition_number
                )

                schema = get_schema(
                    partition_header_dict,
                    session_details,
                    participant_details[car_index],
                )
                table = pa.Table.from_pylist(writer["buffer"], schema)
                parquet_writer = pq.ParquetWriter(
                    output_filepath, schema=schema, compression="snappy"
                )

                parquet_writer.write_table(table)
                parquet_writer.close()
