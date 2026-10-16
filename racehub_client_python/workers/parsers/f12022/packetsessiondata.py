import ctypes
from .packetheader import PacketHeader

NUM_MARSHAL_ZONES = 21
NUM_WEATHER_FORECAST_SAMPLES = 56


class MarshalZone(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_zoneStart", ctypes.c_float),
        ("m_zoneFlag", ctypes.c_int8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class WeatherForecastSample(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_sessionType", ctypes.c_uint8),
        ("m_timeOffset", ctypes.c_uint8),
        ("m_weather", ctypes.c_uint8),
        ("m_trackTemperature", ctypes.c_int8),
        ("m_trackTemperatureChange", ctypes.c_int8),
        ("m_airTemperature", ctypes.c_int8),
        ("m_airTemperatureChange", ctypes.c_int8),
        ("m_rainPercentage", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketSessionData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_weather", ctypes.c_uint8),
        ("m_trackTemperature", ctypes.c_int8),
        ("m_airTemperature", ctypes.c_int8),
        ("m_totalLaps", ctypes.c_uint8),
        ("m_trackLength", ctypes.c_uint16),
        ("m_sessionType", ctypes.c_uint8),
        ("m_trackId", ctypes.c_int8),
        ("m_formula", ctypes.c_uint8),
        ("m_sessionTimeLeft", ctypes.c_uint16),
        ("m_sessionDuration", ctypes.c_uint16),
        ("m_pitSpeedLimit", ctypes.c_uint8),
        ("m_gamePaused", ctypes.c_uint8),
        ("m_isSpectating", ctypes.c_uint8),
        ("m_spectatorCarIndex", ctypes.c_uint8),
        ("m_sliProNativeSupport", ctypes.c_uint8),
        ("m_numMarshalZones", ctypes.c_uint8),
        ("m_marshalZones", MarshalZone * NUM_MARSHAL_ZONES),
        ("m_safetyCarStatus", ctypes.c_uint8),
        ("m_networkGame", ctypes.c_uint8),
        ("m_numWeatherForecastSamples", ctypes.c_uint8),
        (
            "m_weatherForecastSamples",
            WeatherForecastSample * NUM_WEATHER_FORECAST_SAMPLES,
        ),
        ("m_forecastAccuracy", ctypes.c_uint8),
        ("m_aiDifficulty", ctypes.c_uint8),
        ("m_seasonLinkIdentifier", ctypes.c_uint32),
        ("m_weekendLinkIdentifier", ctypes.c_uint32),
        ("m_sessionLinkIdentifier", ctypes.c_uint32),
        ("m_pitStopWindowIdealLap", ctypes.c_uint8),
        ("m_pitStopWindowLatestLap", ctypes.c_uint8),
        ("m_pitStopRejoinPosition", ctypes.c_uint8),
        ("m_steeringAssist", ctypes.c_uint8),
        ("m_brakingAssist", ctypes.c_uint8),
        ("m_gearboxAssist", ctypes.c_uint8),
        ("m_pitAssist", ctypes.c_uint8),
        ("m_pitReleaseAssist", ctypes.c_uint8),
        ("m_ERSAssist", ctypes.c_uint8),
        ("m_DRSAssist", ctypes.c_uint8),
        ("m_dynamicRacingLine", ctypes.c_uint8),
        ("m_dynamicRacingLineType", ctypes.c_uint8),
        ("m_gameMode", ctypes.c_uint8),
        ("m_ruleSet", ctypes.c_uint8),
        ("m_timeOfDay", ctypes.c_uint32),
        ("m_sessionLength", ctypes.c_uint8),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        marshal_zone_columns = {
            f"m_marshalZones_{i}_{field_name}": field_type
            for i in range(NUM_MARSHAL_ZONES)
            for field_name, field_type in MarshalZone().columns().items()
        }
        weather_forecast_sample_columns = {
            f"m_weatherForecastSamples_{i}_{field_name}": field_type
            for i in range(NUM_WEATHER_FORECAST_SAMPLES)
            for field_name, field_type in WeatherForecastSample().columns().items()
        }
        other_columns = {
            field_name: field_type
            for field_name, field_type in self._fields_
            if field_name
            not in ["m_header", "m_marshalZones", "m_weatherForecastSamples"]
        }

        return {
            **header_columns,
            **marshal_zone_columns,
            **weather_forecast_sample_columns,
            **other_columns,
        }

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        marshal_zone_rows = {
            f"m_marshalZones_{i}_{field_name}": value
            for i in range(NUM_MARSHAL_ZONES)
            for field_name, value in self.m_marshalZones[i].row().items()
        }
        weather_forecast_sample_rows = {
            f"m_weatherForecastSamples_{i}_{field_name}": value
            for i in range(NUM_WEATHER_FORECAST_SAMPLES)
            for field_name, value in self.m_weatherForecastSamples[i].row().items()
        }
        other_rows = {
            field_name: getattr(self, field_name)
            for field_name, _ in self._fields_
            if field_name
            not in ["m_header", "m_marshalZones", "m_weatherForecastSamples"]
        }

        return {
            **header_row,
            **marshal_zone_rows,
            **weather_forecast_sample_rows,
            **other_rows,
        }
