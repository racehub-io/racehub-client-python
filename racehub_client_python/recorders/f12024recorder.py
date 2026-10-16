import asyncio
import struct
from datetime import datetime

import racehub_client_python.workers.parsers.f12024 as f12024
from racehub_client_python.workers.parsers.constants import (
    DRIVERS,
    NATIONALITIES,
    SESSION_TYPES,
    TEAMS,
    TRACKS,
)
from racehub_client_python.utils.racehub_pb2 import (
    Participant,
    ParticipantList,
    Session,
    Weather,
    WeatherCondition,
)
from racehub_client_python.recorders.recorder import BaseRecorder
from racehub_client_python.recorders.atlas_tcp.tcp_recorder import TCPRecorder

PARSERS = {
    0: f12024.PacketMotionData,
    1: f12024.PacketSessionData,
    2: f12024.PacketLapData,
    3: f12024.PacketEventData,
    4: f12024.PacketParticipantsData,
    5: f12024.PacketCarSetupData,
    6: f12024.PacketCarTelemetryData,
    7: f12024.PacketCarStatusData,
    8: f12024.PacketFinalClassificationData,
    9: f12024.PacketLobbyInfoData,
    10: f12024.PacketCarDamageData,
    11: f12024.PacketSessionHistoryData,
    12: f12024.PacketTyreSetsData,
    13: f12024.PacketMotionExData,
}

WEATHER_CONDITIONS = {
    0: WeatherCondition.CLEAR,
    1: WeatherCondition.LIGHT_CLOUDS,
    2: WeatherCondition.OVERCAST,
    3: WeatherCondition.LIGHT_RAIN,
    4: WeatherCondition.HEAVY_RAIN,
    5: WeatherCondition.STORM,
}

NUM_CARS = 22

MAX_SPEED_DIFF = 5  # Reduced for less spiky behavior
MIN_TIME_DELTA = 0.001  # 1ms minimum between measurements

telem_message = {
    "timestamp": [datetime.now().timestamp()] * NUM_CARS,
    "session_time": [0.0] * NUM_CARS,
    "distance": [0.0] * NUM_CARS,
    "tyre_sets": [{}] * NUM_CARS,
}


class F12024Recorder(BaseRecorder, TCPRecorder, asyncio.DatagramProtocol):
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
        TCPRecorder.__init__(self)
        self.position_history = [
            {
                "timestamp": 0.0,
                "position": (0.0, 0.0, 0.0),
                "frame_id": 0,
                "last_valid_speed": 0.0,
            }
            for _ in range(NUM_CARS)
        ]

        # For frequency detection
        self.last_frame_time = 0
        self.last_frame_id = 0
        self.frame_count = 0
        self.detected_hz = 0
        self.hz_detection_window = 60

    def detect_frequency(self, current_time, frame_id):
        if self.last_frame_time == 0:
            self.last_frame_time = current_time
            self.last_frame_id = frame_id
            return

        self.frame_count += 1

        if self.frame_count >= self.hz_detection_window:
            time_diff = current_time - self.last_frame_time
            frame_diff = frame_id - self.last_frame_id

            if time_diff > 0:
                hz = frame_diff / time_diff
                # Round to nearest standard frequency
                standard_frequencies = [10, 20, 30, 60]
                self.detected_hz = min(standard_frequencies, key=lambda x: abs(x - hz))

            # Reset for next detection window
            self.last_frame_time = current_time
            self.last_frame_id = frame_id
            self.frame_count = 0

    def calculate_speeds(self, motion_data, game_speeds, frame_id):
        current_timestamp = datetime.now().timestamp()
        speeds_calculated = []

        # Update frequency detection
        self.detect_frequency(current_timestamp, frame_id)
        expected_frame_time = 1.0 / self.detected_hz if self.detected_hz else 1.0 / 60

        for idx, car in enumerate(motion_data):
            x = car.m_worldPositionX
            y = car.m_worldPositionY
            z = car.m_worldPositionZ
            game_speed = game_speeds[idx] if game_speeds else 0

            history = self.position_history[idx]

            if history["timestamp"] > 0:  # If we have previous data
                # Only calculate if this is a new frame and frame_id is greater
                if frame_id != history["frame_id"] and frame_id > history["frame_id"]:
                    prev_pos = history["position"]

                    dx = x - prev_pos[0]
                    dy = y - prev_pos[1]
                    dz = z - prev_pos[2]

                    distance = (dx**2 + dy**2 + dz**2) ** 0.5

                    # Only calculate if we have valid distance
                    if distance > 0:
                        speed = (distance / expected_frame_time) * 3.6  # m/s to km/h

                        # Validate speed against game speed
                        if abs(speed - game_speed) > 50:  # Large difference
                            speed = history["last_valid_speed"] or game_speed
                        else:
                            history["last_valid_speed"] = speed
                    else:
                        speed = history["last_valid_speed"] or game_speed

                    # Update history
                    history["timestamp"] = current_timestamp
                    history["position"] = (x, y, z)
                    history["frame_id"] = frame_id
                else:
                    # Same frame or old frame, use previous valid speed
                    speed = history["last_valid_speed"] or game_speed
            else:
                speed = game_speed
                # Initialize history
                history["timestamp"] = current_timestamp
                history["position"] = (x, y, z)
                history["frame_id"] = frame_id
                history["last_valid_speed"] = game_speed

            speeds_calculated.append(round(speed, 1))

        return speeds_calculated

    def datagram_received(self, data, addr):
        if self.forwardingEnabled:
            self.transport.sendto(data, (self.outAddress, self.outPort))

        self._message_count += 1
        self._last_heartbeat = datetime.now().timestamp()

        header = f12024.PacketHeader.from_buffer_copy(data)

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
            # Get current game speeds if available
            game_speeds = telem_message.get("speed", [0] * NUM_CARS)

            # Calculate speeds using frame ID from header
            speeds_calculated = self.calculate_speeds(
                packet.m_carMotionData, game_speeds, header.m_frameIdentifier
            )

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
                    "lateral_acceleration": [
                        round(car.m_gForceLateral, 1) for car in packet.m_carMotionData
                    ],
                    "longitudinal_acceleration": [
                        round(car.m_gForceLongitudinal, 1)
                        for car in packet.m_carMotionData
                    ],
                    "vertical_acceleration": [
                        round(car.m_gForceVertical, 1) for car in packet.m_carMotionData
                    ],
                    "yaw": [round(car.m_yaw, 1) for car in packet.m_carMotionData],
                    "pitch": [round(car.m_pitch, 1) for car in packet.m_carMotionData],
                    "roll": [round(car.m_roll, 1) for car in packet.m_carMotionData],
                    "speed_calculated": speeds_calculated,
                    "telemetry_hz": self.detected_hz,  # Add detected frequency to telemetry
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

            telem_message.update(
                {
                    "session_time": [round(packet.m_header.m_sessionTime, 1)] * 22,
                    "session_time_left": [round(packet.m_sessionTimeLeft, 1)] * 22,
                    "session_duration": [round(packet.m_sessionDuration, 1)] * 22,
                    "track_temperature": [round(packet.m_trackTemperature, 1)] * 22,
                    "air_temperature": [round(packet.m_airTemperature, 1)] * 22,
                    "total_laps": [int(packet.m_totalLaps)] * 22,
                    "track_length": [round(packet.m_trackLength, 1)] * 22,
                    "pit_speed_limit": [round(packet.m_pitSpeedLimit, 1)] * 22,
                    "safety_car_status": [packet.m_safetyCarStatus] * 22,
                    "weather": [packet.m_weather] * 22,
                    "rain_percentage": [
                        round(packet.m_weatherForecastSamples[0].m_rainPercentage, 1)
                    ]
                    * 22,
                    "pitstop_window_ideal": [round(packet.m_pitStopWindowIdealLap, 1)]
                    * 22,
                    "pitstop_window_latest": [round(packet.m_pitStopWindowLatestLap, 1)]
                    * 22,
                    "pitstop_rejoin_position": [
                        round(packet.m_pitStopRejoinPosition, 1)
                    ]
                    * 22,
                }
            )

            session = Session()
            session.session_id = packet.m_sessionUID
            session.series = packet.m_series
            session.event_name = packet.m_eventName
            session.session_type = SESSION_TYPES.get(packet.m_sessionType, "Unknown")

            number_of_weather_samples = packet.numWeatherForecastSamples
            for i in range(number_of_weather_samples):

                weather = Weather()
                weather.weather_condition = WEATHER_CONDITIONS.get(
                    packet.m_weatherForecastSamples[i].m_weather,
                    WeatherCondition.UNKNOWN,
                )
                weather.time_offset_seconds = packet.m_weatherForecastSamples[
                    i
                ].m_timeOffset
                weather.air_temperature = packet.m_weatherForecastSamples[
                    i
                ].m_airTemperature
                weather.track_temperature = packet.m_weatherForecastSamples[
                    i
                ].m_trackTemperature
                weather.rain_intensity = packet.m_weatherForecastSamples[
                    i
                ].m_rainPercentage
                session.weather.append(weather)

            self.send_proto_message(
                "WORKER_RESPONSE_RECORDER_PROTO_MESSAGE",
                {
                    "recorderId": self.recorder_id,
                    "messageType": "SESSION",
                    "data": session.SerializeToString(),
                },
            )

        elif m_packetId == 2:
            telem_message.update(
                {
                    "lap_distance": [
                        round(car.m_lapDistance, 1) for car in packet.m_lapData
                    ],
                    "distance": [
                        round(car.m_totalDistance, 1) for car in packet.m_lapData
                    ],
                    "current_lap_time": [
                        round((car.m_currentLapTimeInMS / 1000), 3)
                        for car in packet.m_lapData
                    ],
                    "previous_lap_time": [
                        round((car.m_lastLapTimeInMS / 1000), 3)
                        for car in packet.m_lapData
                    ],
                    "grid_position": [car.m_gridPosition for car in packet.m_lapData],
                    "car_position": [car.m_carPosition for car in packet.m_lapData],
                    "lap_number": [car.m_currentLapNum for car in packet.m_lapData],
                    "lap_valid": [car.m_currentLapInvalid for car in packet.m_lapData],
                    "delta_to_leader": [
                        (
                            car.m_deltaToRaceLeaderMinutesPart * 60
                            + car.m_deltaToRaceLeaderMSPart
                        )
                        / 1000
                        for car in packet.m_lapData
                    ],
                    "delta_to_car_ahead": [
                        (
                            car.m_deltaToCarInFrontMinutesPart * 60
                            + car.m_deltaToCarInFrontMSPart
                        )
                        / 1000
                        for car in packet.m_lapData
                    ],
                    "safety_car_delta": [
                        car.m_safetyCarDelta for car in packet.m_lapData
                    ],
                    "pit_status": [car.m_pitStatus for car in packet.m_lapData],
                    "num_pit_stops": [car.m_numPitStops for car in packet.m_lapData],
                    "penalties": [car.m_penalties for car in packet.m_lapData],
                    "total_warnings": [car.m_totalWarnings for car in packet.m_lapData],
                    "corner_cutting_warnings": [
                        car.m_cornerCuttingWarnings for car in packet.m_lapData
                    ],
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

            telem_message.update(
                {
                    "player_car_index": [
                        packet.m_header.m_playerCarIndex for _ in (participants)
                    ],
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

            participant_list = ParticipantList()
            for p in participants:
                participant = Participant()
                participant.index = p["car_index"]
                participant.driver_name.first_name = p["driver_name"].split(" ")[0]
                participant.driver_name.last_name = p["driver_name"].split(" ")[1]
                participant.driver_name.abbreviation = p["driver_abbreviation"]
                participant.car_number = p["driver_number"]
                participant.team_name = p["team_name"]
                participant.nationality = p["driver_nationality"]
                packet.participants.append(participant)

            self.send_proto_message(
                "WORKER_RESPONSE_RECORDER_PROTO_MESSAGE",
                {
                    "recorderId": self.recorder_id,
                    "messageType": "PARTICIPANT_LIST",
                    "data": participant_list.SerializeToString(),
                },
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
                    "timestamp": [datetime.now().timestamp()] * NUM_CARS,
                    "fuel_mix": [car.m_fuelMix for car in packet.m_carStatusData],
                    "fuel_in_tank": [
                        round(car.m_fuelInTank, 2) for car in packet.m_carStatusData
                    ],
                    "fuel_capacity": [
                        round(car.m_fuelCapacity, 2) for car in packet.m_carStatusData
                    ],
                    "fuel_remaining_laps": [
                        round(car.m_fuelRemainingLaps, 2)
                        for car in packet.m_carStatusData
                    ],
                    "max_rpm": [car.m_maxRPM for car in packet.m_carStatusData],
                    "idle_rpm": [car.m_idleRPM for car in packet.m_carStatusData],
                    "drs_allowed": [car.m_DRSAllowed for car in packet.m_carStatusData],
                    "drs_activation_distance": [
                        car.m_DRSActivationDistance for car in packet.m_carStatusData
                    ],
                    "actual_tyre_compound": [
                        car.m_actualTyreCompound for car in packet.m_carStatusData
                    ],
                    "visual_tyre_compound": [
                        car.m_visualTyreCompound for car in packet.m_carStatusData
                    ],
                    "tyre_age_laps": [
                        car.m_tyreAgeLaps for car in packet.m_carStatusData
                    ],
                    "vehicle_fia_flags": [
                        car.m_vehicleFiaFlags for car in packet.m_carStatusData
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
                    "tyres_damage_rl": [
                        car.m_tyresDamageRL for car in packet.m_carDamageData
                    ],
                    "tyres_damage_rr": [
                        car.m_tyresDamageRR for car in packet.m_carDamageData
                    ],
                    "tyres_damage_fl": [
                        car.m_tyresDamageFL for car in packet.m_carDamageData
                    ],
                    "tyres_damage_fr": [
                        car.m_tyresDamageFR for car in packet.m_carDamageData
                    ],
                    "brakes_damage_rl": [
                        car.m_brakesDamageRL for car in packet.m_carDamageData
                    ],
                    "brakes_damage_rr": [
                        car.m_brakesDamageRR for car in packet.m_carDamageData
                    ],
                    "brakes_damage_fl": [
                        car.m_brakesDamageFL for car in packet.m_carDamageData
                    ],
                    "brakes_damage_fr": [
                        car.m_brakesDamageFR for car in packet.m_carDamageData
                    ],
                    "front_left_wing_damage": [
                        car.m_frontLeftWingDamage for car in packet.m_carDamageData
                    ],
                    "front_right_wing_damage": [
                        car.m_frontRightWingDamage for car in packet.m_carDamageData
                    ],
                    "floor_damage": [
                        car.m_floorDamage for car in packet.m_carDamageData
                    ],
                    "diffuser_damage": [
                        car.m_diffuserDamage for car in packet.m_carDamageData
                    ],
                    "sidepod_damage": [
                        car.m_sidepodDamage for car in packet.m_carDamageData
                    ],
                    "drs_fault": [car.m_drsFault for car in packet.m_carDamageData],
                    "ers_fault": [car.m_ersFault for car in packet.m_carDamageData],
                    "gear_box_damage": [
                        car.m_gearBoxDamage for car in packet.m_carDamageData
                    ],
                    "engine_damage": [
                        car.m_engineDamage for car in packet.m_carDamageData
                    ],
                    "engine_mguh_wear": [
                        car.m_engineMGUHWear for car in packet.m_carDamageData
                    ],
                    "engine_es_wear": [
                        car.m_engineESWear for car in packet.m_carDamageData
                    ],
                    "engine_ce_wear": [
                        car.m_engineCEWear for car in packet.m_carDamageData
                    ],
                    "engine_ice_wear": [
                        car.m_engineICEWear for car in packet.m_carDamageData
                    ],
                    "engine_mguk_wear": [
                        car.m_engineMGUKWear for car in packet.m_carDamageData
                    ],
                    "engine_tc_wear": [
                        car.m_engineTCWear for car in packet.m_carDamageData
                    ],
                    "engine_blown": [
                        car.m_engineBlown for car in packet.m_carDamageData
                    ],
                    "engine_seized": [
                        car.m_engineSeized for car in packet.m_carDamageData
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

    def get_latest_telemetry_data(self, client_id: int):
        def get_value(key: str):
            return telem_message.get(key, [0] * NUM_CARS)[client_id]

        return {
            "session_time": get_value("session_time"),
            "session_time_left": get_value("session_time_left"),
            "session_duration": get_value("session_duration"),
            "pit_speed_limit": get_value("pit_speed_limit"),
            "pitstop_window_ideal": get_value("pitstop_window_ideal"),
            "pitstop_window_latest": get_value("pitstop_window_latest"),
            "pitstop_rejoin_position": get_value("pitstop_rejoin_position"),
            "safety_car_status": get_value("safety_car_status"),
            "speed": get_value("speed"),
            "rpm": get_value("rpm"),
            "gear": get_value("gear"),
            "throttle": get_value("throttle") * 100,
            "brake": get_value("brake") * 100,
            "drs": get_value("drs"),
            "steer": get_value("steer") * 360,
            "world_x": get_value("world_x"),
            "world_y": get_value("world_y"),
            "world_z": get_value("world_z"),
            "lateral_acceleration": get_value("lateral_acceleration"),
            "longitudinal_acceleration": get_value("longitudinal_acceleration"),
            "vertical_acceleration": get_value("vertical_acceleration"),
            "yaw": get_value("yaw"),
            "pitch": get_value("pitch"),
            "roll": get_value("roll"),
            "brakes_temperature_rl": get_value("brakes_temperature_rl"),
            "brakes_temperature_rr": get_value("brakes_temperature_rr"),
            "brakes_temperature_fl": get_value("brakes_temperature_fl"),
            "brakes_temperature_fr": get_value("brakes_temperature_fr"),
            "tyres_surface_temperature_rl": get_value("tyres_surface_temperature_rl"),
            "tyres_surface_temperature_rr": get_value("tyres_surface_temperature_rr"),
            "tyres_surface_temperature_fl": get_value("tyres_surface_temperature_fl"),
            "tyres_surface_temperature_fr": get_value("tyres_surface_temperature_fr"),
            "tyres_inner_temperature_rl": get_value("tyres_inner_temperature_rl"),
            "tyres_inner_temperature_rr": get_value("tyres_inner_temperature_rr"),
            "tyres_inner_temperature_fl": get_value("tyres_inner_temperature_fl"),
            "tyres_inner_temperature_fr": get_value("tyres_inner_temperature_fr"),
            "engine_temperature": get_value("engine_temperature"),
            "tyres_pressure_rl": get_value("tyres_pressure_rl"),
            "tyres_pressure_rr": get_value("tyres_pressure_rr"),
            "tyres_pressure_fl": get_value("tyres_pressure_fl"),
            "tyres_pressure_fr": get_value("tyres_pressure_fr"),
            "fuel_mix": get_value("fuel_mix"),
            "fuel_in_tank": get_value("fuel_in_tank"),
            "fuel_capacity": get_value("fuel_capacity"),
            "fuel_remaining_laps": get_value("fuel_remaining_laps"),
            "max_rpm": get_value("max_rpm"),
            "idle_rpm": get_value("idle_rpm"),
            "drs_allowed": get_value("drs_allowed"),
            "drs_activation_distance": get_value("drs_activation_distance"),
            "actual_tyre_compound": get_value("actual_tyre_compound"),
            "visual_tyre_compound": get_value("visual_tyre_compound"),
            "tyre_age_laps": get_value("tyre_age_laps"),
            "vehicle_fia_flags": get_value("vehicle_fia_flags"),
            "ers_store_energy": get_value("ers_store_energy") / 1e3,
            "ers_deploy_mode": get_value("ers_deploy_mode"),
            "ers_harvested_this_lap_mguk": get_value("ers_harvested_this_lap_mguk")
            / 1e3,
            "ers_harvested_this_lap_mguh": get_value("ers_harvested_this_lap_mguh")
            / 1e3,
            "ers_deployed_this_lap": get_value("ers_deployed_this_lap") / 1e3,
            "tyres_wear_rl": get_value("tyres_wear_rl"),
            "tyres_wear_rr": get_value("tyres_wear_rr"),
            "tyres_wear_fl": get_value("tyres_wear_fl"),
            "tyres_wear_fr": get_value("tyres_wear_fr"),
            "tyres_damage_rl": get_value("tyres_damage_rl"),
            "tyres_damage_rr": get_value("tyres_damage_rr"),
            "tyres_damage_fl": get_value("tyres_damage_fl"),
            "tyres_damage_fr": get_value("tyres_damage_fr"),
            "brakes_damage_rl": get_value("brakes_damage_rl"),
            "brakes_damage_rr": get_value("brakes_damage_rr"),
            "brakes_damage_fl": get_value("brakes_damage_fl"),
            "brakes_damage_fr": get_value("brakes_damage_fr"),
            "front_left_wing_damage": get_value("front_left_wing_damage"),
            "front_right_wing_damage": get_value("front_right_wing_damage"),
            "floor_damage": get_value("floor_damage"),
            "diffuser_damage": get_value("diffuser_damage"),
            "sidepod_damage": get_value("sidepod_damage"),
            "drs_fault": get_value("drs_fault"),
            "ers_fault": get_value("ers_fault"),
            "gear_box_damage": get_value("gear_box_damage"),
            "engine_damage": get_value("engine_damage"),
            "engine_mguh_wear": get_value("engine_mguh_wear"),
            "engine_es_wear": get_value("engine_es_wear"),
            "engine_ce_wear": get_value("engine_ce_wear"),
            "engine_ice_wear": get_value("engine_ice_wear"),
            "engine_mguk_wear": get_value("engine_mguk_wear"),
            "engine_tc_wear": get_value("engine_tc_wear"),
            "engine_blown": get_value("engine_blown"),
            "engine_seized": get_value("engine_seized"),
            "track_temperature": get_value("track_temperature"),
            "air_temperature": get_value("air_temperature"),
            "total_laps": get_value("total_laps"),
            "track_length": get_value("track_length"),
            "weather": get_value("weather"),
            "rain_percentage": get_value("rain_percentage"),
            "lap_distance": get_value("lap_distance"),
            "distance": get_value("distance"),
            "current_lap_time": get_value("current_lap_time"),
            "previous_lap_time": get_value("previous_lap_time"),
            "grid_position": get_value("grid_position"),
            "car_position": get_value("car_position"),
            "lap_number": get_value("lap_number"),
            "lap_valid": get_value("lap_valid"),
            "player_car_index": get_value("player_car_index"),
            "car_index": get_value("car_index"),
            "delta_to_leader": get_value("delta_to_leader"),
            "delta_to_car_ahead": get_value("delta_to_car_ahead"),
            "safety_car_delta": get_value("safety_car_delta"),
            "pit_status": get_value("pit_status"),
            "num_pit_stops": get_value("num_pit_stops"),
            "penalties": get_value("penalties"),
            "total_warnings": get_value("total_warnings"),
            "corner_cutting_warnings": get_value("corner_cutting_warnings"),
            "driver_number": get_value("driver_number"),
        }


def test():
    # add this to pyproject.toml
    # test = "racehub_client_python.recorders.iracingrecorder:test"
    # Configure logging
    import logging
    import socket

    logging.basicConfig(level=logging.INFO)

    # For testing
    recorder_id = "recorder--1"
    recorderType = "f12024"
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
        lambda: F12024Recorder(
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
