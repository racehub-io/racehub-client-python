import ctypes
import datetime as dt
import json
import pyarrow as pa
import pyarrow.parquet as pq

from racehub_client_python.workers.parsers import BaseParser, get_output_filepath
from racehub_client_python.workers.websockets import send_message
import racehub_client_python.workers.parsers.f12022 as f12022
from racehub_client_python.workers.parsers.constants import (
    DRIVERS,
    FORMULA,
    GAME_MODES,
    NATIONALITIES,
    SESSION_TYPES,
    TEAMS,
    TRACKS,
)
from racehub_client_python.utils.ctypesconversions import CTYPES_TO_PYARROW_MAP

PARSERS = {
    0: f12022.PacketMotionData,
    1: f12022.PacketSessionData,
    2: f12022.PacketLapData,
    # 3: f12022.PacketEventData,
    4: f12022.PacketParticipantsData,
    5: f12022.PacketCarSetupData,
    6: f12022.PacketCarTelemetryData,
    7: f12022.PacketCarStatusData,
    8: f12022.PacketFinalClassificationData,
    9: f12022.PacketLobbyInfoData,
    10: f12022.PacketCarDamageData,
    11: f12022.PacketSessionHistoryData,
    "header": f12022.PacketHeader,
}

NUM_CARS = 22


def get_schema(file_details={}, session_details={}, participant_details={}):
    fields_dict = {}

    for packet_id, packet_class in PARSERS.items():
        if packet_id == "header":
            continue

        packet_instance = packet_class()
        for field_name, field_type in packet_instance.columns().items():
            if field_type.__name__.startswith("c_char_Array"):
                pyarrow_type = pa.string()
            else:
                pyarrow_type = CTYPES_TO_PYARROW_MAP.get(field_type)

            fields_dict[field_name] = pyarrow_type

    fields = [pa.field(name, type_) for name, type_ in fields_dict.items()]
    metadata = {
        **file_details,
        **session_details,
        **participant_details,
    }

    metadata = {b"racehub": json.dumps(metadata)}

    return pa.schema(fields, metadata=metadata)


class F12022Parser(BaseParser):
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
                "active_row": {},
                "buffer": [],
                "active": False,
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

        processed_packet_ids = set()
        session_history_buffer = []

        current_frame = None

        next_progress_threshold = 0

        # get the initial empty row
        def get_empty_row():
            from racehub_client_python.workers.parsers.f12022 import get_column_types

            columns = get_column_types()
            return {column: None for column in columns}

        for car_index in range(NUM_CARS):
            row = get_empty_row()
            writers[car_index]["active_row"] = row

        while True:
            # Read the packet length and data
            length_data = self.partition_file.read(2)
            if not length_data:
                break

            packet_length = int.from_bytes(length_data, "little")

            position = self.partition_file.tell()

            header_data = self.partition_file.read(ctypes.sizeof(f12022.PacketHeader))
            header = f12022.PacketHeader.from_buffer_copy(header_data)

            # Extract the information you need
            m_frameIdentifier = header.m_frameIdentifier
            m_packetId = header.m_packetId
            m_sessionUID = header.m_sessionUID

            # Return to the saved position
            self.partition_file.seek(position)

            if current_frame != m_frameIdentifier:
                current_frame = m_frameIdentifier
                for car_index, writer in writers.items():
                    if not writer["active"]:
                        continue

                    writers[car_index]["buffer"].append(
                        writers[car_index]["active_row"].copy()
                    )

            if m_packetId == 11:
                session_history_buffer.append(self.partition_file.read(packet_length))

                if len(session_history_buffer) > NUM_CARS:
                    session_history_buffer.pop(0)

            else:
                parser = PARSERS.get(m_packetId)

                if parser and packet_length >= ctypes.sizeof(parser):
                    packet_data = self.partition_file.read(ctypes.sizeof(parser))
                    packet = parser.from_buffer_copy(packet_data)

                    for car_index, writer in writers.items():
                        if not writer["active"]:
                            continue

                        packet_row = packet.row(car_index)
                        writers[car_index]["active_row"].update(packet_row)

                    if m_packetId not in processed_packet_ids:
                        if m_packetId == 1:
                            session_details.update(
                                {
                                    "session_id": m_sessionUID,
                                    "series": FORMULA.get(packet.m_formula, "Unknown"),
                                    "event_name": GAME_MODES.get(
                                        packet.m_gameMode, "Unknown"
                                    ),
                                    "session_name": SESSION_TYPES.get(
                                        packet.m_sessionType, "Unknown"
                                    ),
                                    "track_name": TRACKS.get(
                                        packet.m_trackId, "Unknown"
                                    ),
                                    "track_length": packet.m_trackLength,
                                    "air_temp": packet.m_airTemperature,
                                    "track_temp": packet.m_trackTemperature,
                                    "vehicle_type": FORMULA.get(
                                        packet.m_formula, "Unknown"
                                    ),
                                }
                            )
                        elif m_packetId == 4:
                            for car_index, writer in writers.items():
                                writers[car_index]["active"] = (
                                    False
                                    if packet.m_participantsData[
                                        car_index
                                    ].m_aiControlled
                                    or packet.m_participantsData[car_index].m_raceNumber
                                    == 0
                                    else True
                                )

                            for car_index in range(NUM_CARS):
                                driver = DRIVERS.get(
                                    packet.m_participantsData[car_index].m_driverId,
                                    DRIVERS["default"],
                                )
                                participant_details[car_index].update(
                                    {
                                        "player_name": packet.m_participantsData[
                                            car_index
                                        ].m_name.decode("utf-8"),
                                        "driver_name": "{first_name} {last_name}".format(
                                            **driver
                                        ),
                                        "driver_abbreviation": driver["abbreviation"],
                                        "driver_number": packet.m_participantsData[
                                            car_index
                                        ].m_raceNumber,
                                        "driver_nationality": NATIONALITIES.get(
                                            packet.m_participantsData[
                                                car_index
                                            ].m_nationality,
                                            "Unknown",
                                        ),
                                        "team_name": TEAMS.get(
                                            packet.m_participantsData[
                                                car_index
                                            ].m_teamId,
                                            "Unknown",
                                        ),
                                        "vehicle_comment": TEAMS.get(
                                            packet.m_participantsData[
                                                car_index
                                            ].m_teamId,
                                            "Unknown",
                                        ),
                                    }
                                )

                        # Remember that we've processed this packet type
                        processed_packet_ids.add(m_packetId)

                    self.partition_file.read(packet_length - ctypes.sizeof(parser))
                else:
                    self.partition_file.read(packet_length)

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

        for session_history_data in session_history_buffer:
            header_data = session_history_data[0 : ctypes.sizeof(f12022.PacketHeader)]
            header = f12022.PacketHeader.from_buffer_copy(header_data)

            # Extract the information you need
            m_frameIdentifier = header.m_frameIdentifier
            m_packetId = header.m_packetId
            m_sessionUID = header.m_sessionUID

            packet = f12022.PacketSessionHistoryData.from_buffer_copy(
                session_history_data
            )

            laps = [
                {
                    "lap_time": lap.m_lapTimeInMS,
                    "sector_1_time": lap.m_sector1TimeInMS,
                    "sector_2_time": lap.m_sector2TimeInMS,
                    "sector_3_time": lap.m_sector3TimeInMS,
                    "lap_valid": lap.m_lapValidBitFlags,
                }
                for lap in packet.m_lapHistoryData
                if lap.m_lapTimeInMS > 0
            ]

            tyres = [
                {
                    "end_lap": tyre.m_endLap,
                    "actual_compound": tyre.m_tyreActualCompound,
                    "visual_compound": tyre.m_tyreVisualCompound,
                }
                for tyre in packet.m_tyreStintsHistoryData
                if tyre.m_endLap > 0
            ]

            participant_details[packet.m_carIdx].update(
                {
                    "laps": laps,
                    "tyres": tyres,
                }
            )

        for car_index, writer in writers.items():
            if writer["buffer"]:
                output_filepath = get_output_filepath(
                    recorder_name,
                    partition_timestamp,
                    car_index,
                    partition_number,
                )

                schema = get_schema(
                    partition_header_dict,
                    session_details,
                    participant_details[car_index],
                )

                table = pa.Table.from_pylist(
                    writers[car_index]["buffer"],
                    schema,
                )

                parquet_writer = pq.ParquetWriter(
                    output_filepath,
                    compression="snappy",
                    schema=schema,
                )

                # write to parquet
                parquet_writer.write_table(table)

                parquet_writer.close()
