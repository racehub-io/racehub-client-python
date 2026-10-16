import asyncio
import struct
import datetime as dt

import racehub_client_python.workers.parsers.f12023 as f12023
from racehub_client_python.workers.parsers.constants import (
    DRIVERS,
    FORMULA,
    GAME_MODES,
    NATIONALITIES,
    SESSION_TYPES,
    TEAMS,
    TRACKS,
)
from racehub_client_python.recorders.recorder import BaseRecorder

PARSERS = {
    0: f12023.PacketMotionData,
    1: f12023.PacketSessionData,
    2: f12023.PacketLapData,
    3: f12023.PacketEventData,
    4: f12023.PacketParticipantsData,
    5: f12023.PacketCarSetupData,
    6: f12023.PacketCarTelemetryData,
    7: f12023.PacketCarStatusData,
    8: f12023.PacketFinalClassificationData,
    9: f12023.PacketLobbyInfoData,
    10: f12023.PacketCarDamageData,
    11: f12023.PacketSessionHistoryData,
    12: f12023.PacketTyreSetsData,
    13: f12023.PacketMotionExData,
}


telem_message = {
    "tyre_sets": [{}] * 22,
}


class F12023Recorder(BaseRecorder, asyncio.DatagramProtocol):
    def __init__(
        self, recorder_id, recorderType, loop, outAddress, outPort, forwardingEnabled
    ):
        BaseRecorder.__init__(
            self,
            recorder_id,
            recorderType,
            loop,
            outAddress,
            outPort,
            forwardingEnabled,
        )

    def datagram_received(self, data, addr):
        if self.forwardingEnabled:
            self.transport.sendto(data, (self.outAddress, self.outPort))

        self._message_count += 1
        self._last_heartbeat = dt.datetime.now().timestamp()

        header = f12023.PacketHeader.from_buffer_copy(data)

        m_packetId = header.m_packetId
        m_sessionUID = header.m_sessionUID

        if (not self._archive_path) and (m_sessionUID != 0):
            self.create_archive()
            self.create_partition()

        elif (m_sessionUID != self.current_session_id) and (m_sessionUID != 0):
            if self._archive_path:
                self.close_partition()
                self.close_archive()
            else:
                self.create_archive()
            self.create_partition()

        elif (m_sessionUID == 0) and (self._archive_path):
            self.close_partition()
            self.close_archive()

        self.current_session_id = m_sessionUID

        if (self._archive_path) and (not self._partition_gz_file):
            self.create_partition()
        else:
            # if the self._message_count has just passed an interval of 20e3, close the file and create a new one
            if self._message_count % 50e3 == 0:
                self.close_partition()
                self.create_partition()

        if self._partition_gz_file and not self._partition_gz_file.closed:
            # get the size of the packet
            mSize = struct.pack("H", len(data))
            self._partition_gz_file.write(mSize)
            self._partition_gz_file.write(data)

        # These packet types take too long to parse
        if m_packetId not in [0, 1, 2, 4, 6, 7, 10, 12]:
            return

        parser = PARSERS[m_packetId]
        packet = parser.from_buffer_copy(data)

        if m_packetId == 0:
            telem_message.update(
                {
                    "world_x": [
                        round(car.m_worldPositionX, 1) for car in packet.m_carMotionData
                    ],
                    "world_y": [
                        round(car.m_worldPositionY, 1) for car in packet.m_carMotionData
                    ],
                    "world_z": [
                        round(car.m_worldPositionZ, 1) for car in packet.m_carMotionData
                    ],
                }
            )

        elif m_packetId == 1:
            payload = {
                "recorderId": self.recorder_id,
                "message_count": self._message_count,
                "last_heartbeat": self._last_heartbeat,
                "session_time": packet.m_header.m_sessionTime,
                "session_type": SESSION_TYPES.get(packet.m_sessionType, "Unknown"),
                "track_name": TRACKS.get(packet.m_trackId, "Unknown"),
            }
            self.send_message("WORKER_RESPONSE_RECORDER_STATUS", payload)

            # Update the current session metadata
            self.session_metadata.update(
                {
                    "session_id": m_sessionUID,
                    "series": FORMULA.get(packet.m_formula, "Unknown"),
                    "event_name": GAME_MODES.get(packet.m_gameMode, "Unknown"),
                    "session_name": SESSION_TYPES.get(packet.m_sessionType, "Unknown"),
                    "track_name": TRACKS.get(packet.m_trackId, "Unknown"),
                    "track_length": packet.m_trackLength,
                    "air_temp": packet.m_airTemperature,
                    "track_temp": packet.m_trackTemperature,
                    "vehicle_type": FORMULA.get(packet.m_formula, "Unknown"),
                }
            )

            telem_message.update(
                {
                    "session_time": [round(packet.m_header.m_sessionTime, 1)] * 22,
                    "track_temperature": [round(packet.m_trackTemperature, 1)] * 22,
                    "air_temperature": [round(packet.m_airTemperature, 1)] * 22,
                    "total_laps": [int(packet.m_totalLaps)] * 22,
                    "track_length": [round(packet.m_trackLength, 1)] * 22,
                    "weather": [packet.m_weather] * 22,
                    "rain_percentage": [
                        round(packet.m_weatherForecastSamples[0].m_rainPercentage, 1)
                    ]
                    * 22,
                }
            )

        elif m_packetId == 2:
            telem_message.update(
                {
                    "lap_distance": [
                        round(car.m_lapDistance, 1) for car in packet.m_lapData
                    ],
                    "current_lap_time": [
                        round((car.m_currentLapTimeInMS / 1000), 3)
                        for car in packet.m_lapData
                    ],
                    "previous_lap_time": [
                        round((car.m_lastLapTimeInMS / 1000), 3)
                        for car in packet.m_lapData
                    ],
                    "car_position": [car.m_carPosition for car in packet.m_lapData],
                    "lap_number": [car.m_currentLapNum for car in packet.m_lapData],
                    "lap_valid": [car.m_currentLapInvalid for car in packet.m_lapData],
                }
            )

        elif m_packetId == 4:
            formatted_drivers = [
                DRIVERS.get(
                    participant.m_driverId,
                    {"first_name": "First", "last_name": "Last", "abbreviation": "DRV"},
                )
                for participant in packet.m_participantsData
            ]

            participants = [
                {
                    "car_index": carIdx,
                    "player_name": participant.m_name.decode("utf-8"),
                    "driver_name": "{first_name} {last_name}".format(
                        **formatted_drivers[carIdx]
                    ),
                    "driver_abbreviation": formatted_drivers[carIdx]["abbreviation"],
                    "driver_number": participant.m_raceNumber,
                    "driver_nationality": NATIONALITIES.get(
                        participant.m_nationality,
                        "Unknown",
                    ),
                    "team_name": TEAMS.get(
                        participant.m_teamId,
                        "Unknown",
                    ),
                    "vehicle_comment": TEAMS.get(
                        participant.m_teamId,
                        "Unknown",
                    ),
                }
                for carIdx, participant in enumerate(packet.m_participantsData)
            ]

            self.session_metadata.update(
                {
                    "participants": participants,
                }
            )

            telem_message.update(
                {
                    "car_index": [p["car_index"] for p in (participants)],
                    "player_name": [p["player_name"] for p in (participants)],
                    "driver_name": [p["driver_name"] for p in (participants)],
                    "driver_abbreviation": [
                        p["driver_abbreviation"] for p in (participants)
                    ],
                    "driver_number": [p["driver_number"] for p in (participants)],
                    "driver_nationality": [
                        p["driver_nationality"] for p in (participants)
                    ],
                    "team_name": [p["team_name"] for p in (participants)],
                    "vehicle_comment": [p["vehicle_comment"] for p in (participants)],
                }
            )

        elif m_packetId == 6:
            telem_message.update(
                {
                    "speed": [car.m_speed for car in packet.m_carTelemetryData],
                    "throttle": [
                        round(car.m_throttle, 2) for car in packet.m_carTelemetryData
                    ],
                    "brake": [
                        round(car.m_brake, 2) for car in packet.m_carTelemetryData
                    ],
                    "steer": [
                        round(car.m_steer, 2) for car in packet.m_carTelemetryData
                    ],
                    "gear": [car.m_gear for car in packet.m_carTelemetryData],
                    "drs": [car.m_drs for car in packet.m_carTelemetryData],
                    "brakes_temperature_rl": [
                        car.m_brakesTemperatureRL for car in packet.m_carTelemetryData
                    ],
                    "brakes_temperature_rr": [
                        car.m_brakesTemperatureRR for car in packet.m_carTelemetryData
                    ],
                    "brakes_temperature_fl": [
                        car.m_brakesTemperatureFL for car in packet.m_carTelemetryData
                    ],
                    "brakes_temperature_fr": [
                        car.m_brakesTemperatureFR for car in packet.m_carTelemetryData
                    ],
                    "tyres_surface_temperature_rl": [
                        car.m_tyresSurfaceTemperatureRL
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_surface_temperature_rr": [
                        car.m_tyresSurfaceTemperatureRR
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_surface_temperature_fl": [
                        car.m_tyresSurfaceTemperatureFL
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_surface_temperature_fr": [
                        car.m_tyresSurfaceTemperatureFR
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_inner_temperature_rl": [
                        car.m_tyresInnerTemperatureRL
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_inner_temperature_rr": [
                        car.m_tyresInnerTemperatureRR
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_inner_temperature_fl": [
                        car.m_tyresInnerTemperatureFL
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_inner_temperature_fr": [
                        car.m_tyresInnerTemperatureFR
                        for car in packet.m_carTelemetryData
                    ],
                    "engine_temperature": [
                        car.m_engineTemperature for car in packet.m_carTelemetryData
                    ],
                    "tyres_pressure_rl": [
                        round(car.m_tyresPressureRL, 1)
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_pressure_rr": [
                        round(car.m_tyresPressureRR, 1)
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_pressure_fl": [
                        round(car.m_tyresPressureFL, 1)
                        for car in packet.m_carTelemetryData
                    ],
                    "tyres_pressure_fr": [
                        round(car.m_tyresPressureFR, 1)
                        for car in packet.m_carTelemetryData
                    ],
                }
            )

        elif m_packetId == 7:
            telem_message.update(
                {
                    "fuel_in_tank": [
                        round(car.m_fuelInTank, 2) for car in packet.m_carStatusData
                    ],
                    "ers_store_energy": [
                        round(car.m_ersStoreEnergy, 2) for car in packet.m_carStatusData
                    ],
                    "ers_deploy_mode": [
                        car.m_ersDeployMode for car in packet.m_carStatusData
                    ],
                    "ers_harvested_this_lap_mguk": [
                        round(car.m_ersHarvestedThisLapMGUK, 1)
                        for car in packet.m_carStatusData
                    ],
                    "ers_harvested_this_lap_mguh": [
                        round(car.m_ersHarvestedThisLapMGUH, 1)
                        for car in packet.m_carStatusData
                    ],
                    "ers_deployed_this_lap": [
                        round(car.m_ersDeployedThisLap, 1)
                        for car in packet.m_carStatusData
                    ],
                }
            )

            # send the message every tenth frame and embed the check in here as there are a number of packets sent on the same frame
            # so this is to only do it once
            if packet.m_header.m_frameIdentifier % 2 == 0:
                self.send_telem_message(telem_message)

        elif m_packetId == 10:
            telem_message.update(
                {
                    "tyres_wear_rl": [
                        round(car.m_tyresWearRL, 2) for car in packet.m_carDamageData
                    ],
                    "tyres_wear_rr": [
                        round(car.m_tyresWearRR, 2) for car in packet.m_carDamageData
                    ],
                    "tyres_wear_fl": [
                        round(car.m_tyresWearFL, 2) for car in packet.m_carDamageData
                    ],
                    "tyres_wear_fr": [
                        round(car.m_tyresWearFR, 2) for car in packet.m_carDamageData
                    ],
                }
            )

        elif m_packetId == 12:
            car_index = packet.m_carIdx

            telem_message["tyre_sets"][car_index] = [
                {
                    "wear": tyre_set_data.m_wear,
                    "available": tyre_set_data.m_available,
                    "life_span": tyre_set_data.m_lifeSpan,
                    "usable_life": tyre_set_data.m_usableLife,
                    "lap_delta_time": tyre_set_data.m_lapDeltaTime,
                    "fitted": tyre_set_data.m_fitted,
                }
                for tyre_set_data in packet.m_tyreSetData
            ]


def test():
    # add this to pyproject.toml
    # test = "racehub_client_python.recorders.iracingrecorder:test"
    # Configure logging
    import logging
    import socket

    logging.basicConfig(level=logging.INFO)

    # For testing
    recorder_id = "recorder--1"
    recorderType = "f12023"
    inPort = 30500
    outAddress = ""
    outPort = 30501
    forwardingEnabled = False

    loop = asyncio.get_event_loop()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("127.0.0.1", inPort))

    # One protocol instance will be created to serve all client requests
    listen = loop.create_datagram_endpoint(
        lambda: F12023Recorder(
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
