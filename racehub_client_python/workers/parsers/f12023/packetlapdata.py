import ctypes
from .packetheader import PacketHeader


class LapData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_lastLapTimeInMS", ctypes.c_uint32),
        ("m_currentLapTimeInMS", ctypes.c_uint32),
        ("m_sector1TimeinMS", ctypes.c_uint16),
        ("m_sector1TimeInMinutes", ctypes.c_uint8),
        ("m_sector2TimeinMS", ctypes.c_uint16),
        ("m_sector2TimeInMinutes", ctypes.c_uint8),
        ("m_deltaToCarInFrontInMS", ctypes.c_uint16),
        ("m_deltaToRaceLeaderInMS", ctypes.c_uint16),
        ("m_lapDistance", ctypes.c_float),
        ("m_totalDistance", ctypes.c_float),
        ("m_safetyCarDelta", ctypes.c_float),
        ("m_carPosition", ctypes.c_uint8),
        ("m_currentLapNum", ctypes.c_uint8),
        ("m_pitStatus", ctypes.c_uint8),
        ("m_numPitStops", ctypes.c_uint8),
        ("m_sector", ctypes.c_uint8),
        ("m_currentLapInvalid", ctypes.c_uint8),
        ("m_penalties", ctypes.c_uint8),
        ("m_totalWarnings", ctypes.c_uint8),
        ("m_cornerCuttingWarnings", ctypes.c_uint8),
        ("m_numUnservedDriveThroughPens", ctypes.c_uint8),
        ("m_numUnservedStopGoPens", ctypes.c_uint8),
        ("m_gridPosition", ctypes.c_uint8),
        ("m_driverStatus", ctypes.c_uint8),
        ("m_resultStatus", ctypes.c_uint8),
        ("m_pitLaneTimerActive", ctypes.c_uint8),
        ("m_pitLaneTimeInLaneInMS", ctypes.c_uint16),
        ("m_pitStopTimerInMS", ctypes.c_uint16),
        ("m_pitStopShouldServePen", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketLapData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_lapData", LapData * 22),
        ("m_timeTrialPBCarIdx", ctypes.c_uint8),
        ("m_timeTrialRivalCarIdx", ctypes.c_uint8),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        lap_data_columns = {
            f"m_lapData_{field_name}": field_type
            for field_name, field_type in LapData().columns().items()
        }
        return {
            **header_columns,
            **lap_data_columns,
            "m_timeTrialPBCarIdx": ctypes.c_uint8,
            "m_timeTrialRivalCarIdx": ctypes.c_uint8,
        }

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        lap_data_row = {
            f"m_lapData_{field_name}": value
            for field_name, value in self.m_lapData[car_index].row().items()
        }
        return {
            **header_row,
            **lap_data_row,
            "m_timeTrialPBCarIdx": self.m_timeTrialPBCarIdx,
            "m_timeTrialRivalCarIdx": self.m_timeTrialRivalCarIdx,
        }
