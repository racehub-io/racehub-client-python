import asyncio
import datetime as dt
import struct

from racehub_client_python.recorders.recorder import BaseRecorder
import racehub_client_python.utils.iracing_message_pb2 as iRacingProto

import racehub_client_python.utils.racehub_pb2 as RaceHubMessage

telem_message = {}


class iRacingRecorder(BaseRecorder, asyncio.DatagramProtocol):
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

        self.previous_timestamp = None
        self.distances = []

    def datagram_received(self, data, addr):
        if self.forwardingEnabled:
            self.transport.sendto(data, (self.outAddress, self.outPort))

        timestamp = dt.datetime.now().timestamp()

        self._message_count += 1
        self._last_heartbeat = timestamp

        # parse the data
        packet = iRacingProto.iRacingMessage()
        packet.ParseFromString(data)

        cars = packet.cars
        participants = packet.participants
        session_info = packet.session

        session_id = session_info.session_id

        if not self._archive_path:
            self.create_archive()
            self.create_partition()
        elif session_id != self.current_session_id:
            if self._archive_path:
                self.close_partition()
                self.close_archive()
            else:
                self.create_archive()
            self.create_partition()

        self.current_session_id = session_id

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

        telemetry_packet = RaceHubMessage.Telemetry()

        # add all the cars
        for n, car in enumerate(cars):
            telem_car = telemetry_packet.cars.add()
            telem_car.timestamp = int(dt.datetime.now().timestamp())

            # total distance calculations
            speed = car.speed
            if self.previous_timestamp is not None and len(self.distances) > (n - 1):
                distance = self.distances[n] + speed / (
                    timestamp - self.previous_timestamp
                )
                self.distances[n] = distance
            else:
                distance = speed / timestamp
                self.distances.append(distance)

            self.previous_timestamp = timestamp

            telem_car.distance = distance
            telem_car.speed = speed
            telem_car.throttle = car.throttle
            telem_car.brake = car.brake
            telem_car.clutch = car.clutch
            telem_car.gear = car.gear
            telem_car.engine_rpm = car.engine_rpm
            telem_car.steering_angle = car.steering_angle
            telem_car.lap_time = car.lap_time

            # lap_distance_pct = car.LapDistancePct
            # telem_car.lap_distance = lap_distance_pct * session_info.TrackLength

        self.send_proto_message(
            "TELEMETRY",
            telemetry_packet.SerializeToString(),
        )

        telem_message.update(
            {
                "timestamp": [timestamp for car in cars],
                "distance": [self.distances[n] for n, car in enumerate(cars)],
                # "AirDensity": [session_info.AirDensity for car in cars],
                # "AirPressure": [session_info.AirPressure for car in cars],
                "air_temperature": [session_info.air_temperature for car in cars],
                "brake": [car.brake for car in cars],
                "clutch": [car.clutch for car in cars],
                "gear": [car.gear for car in cars],
                "car_index": [car.car_index for car in cars],
                "player_name": [
                    participant.driver_name for participant in participants
                ],
                "driver_name": [
                    participant.driver_name for participant in participants
                ],
                "driver_abbreviation": [
                    participant.abbreviation for participant in participants
                ],
                "driver_number": [
                    participant.car_number for participant in participants
                ],
                "driver_nationality": [""] * len(participants),
                "team_name": [participant.team_name for participant in participants],
                "lap_number": [car.lap_number for car in cars],
                "lap_time": [car.lap_time for car in cars],
                # "LapDistancePct": [car.LapDistancePct for car in cars],
                "engine_rpm": [car.engine_rpm for car in cars],
                "session_time_elapsed": [
                    session_info.session_time_elapsed for car in cars
                ],
                "speed": [car.speed for car in cars],
                "steering_angle": [car.steering_angle for car in cars],
                "throttle": [car.throttle for car in cars],
                "track_temperature": [session_info.track_temperature for car in cars],
                # "TrackWetness": [session_info.TrackWetness for car in cars],
            }
        )

        self.send_telem_message(telem_message)

        if self._message_count % 10 == 0:
            payload = {
                "recorderId": self.recorder_id,
                "message_count": self._message_count,
                "last_heartbeat": self._last_heartbeat,
                "session_time": session_info.session_time_elapsed,
                "session_type": session_info.session_type,
                "track_name": session_info.track_name,
            }
            self.send_message("WORKER_RESPONSE_RECORDER_STATUS", payload)

            session_packet = RaceHubMessage.Session()
            session_packet.session_id = session_info.session_id
            session_packet.series = session_info.series
            session_packet.event_name = session_info.event_name
            session_packet.session_type = session_info.session_type
            session_packet.session_time_elapsed = session_info.session_time_elapsed
            session_packet.track_name = session_info.track_name
            session_packet.track_length = session_info.track_length
            session_packet.air_temperature = session_info.air_temperature
            session_packet.track_temperature = session_info.track_temperature
            session_packet.rain_intensity = session_info.rain_intensity

            self.send_proto_message(
                "SESSION",
                session_packet.SerializeToString(),
            )


def test():
    # add this to pyproject.toml
    # test = "racehub_client_python.recorders.iracingrecorder:test"
    # Configure logging
    import logging
    import socket

    logging.basicConfig(level=logging.INFO)

    # For testing
    recorder_id = "recorder--1"
    recorderType = "iRacing"
    inPort = 20900
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
        lambda: iRacingRecorder(
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
