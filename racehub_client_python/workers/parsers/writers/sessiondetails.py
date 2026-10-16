import datetime as dt


class SessionDetails(object):
    def __init__(
        self,
        session_timestamp=dt.datetime.now().timestamp(),
        series="",
        event_name="",
        session_name="",
        vehicle_type="",
        vehicle_comment="",
        track_name="",
        track_length=0,
        air_temp=0,
        track_temp=0,
        driver_name="",
        driver_abbreviation="",
        driver_number=0,
        driver_nationality="",
        team_name="",
    ):
        self.session_timestamp = session_timestamp
        self.event_name = event_name
        self.session_name = session_name
        self.series = series
        self.vehicle_type = vehicle_type
        self.vehicle_comment = vehicle_comment
        self.track_name = track_name
        self.track_length = track_length
        self.air_temp = air_temp
        self.track_temp = track_temp
        self.driver_name = driver_name
        self.driver_abbreviation = driver_abbreviation
        self.driver_number = driver_number
        self.driver_nationality = driver_nationality
        self.team_name = team_name
