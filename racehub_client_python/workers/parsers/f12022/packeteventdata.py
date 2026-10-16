import ctypes
from .packetheader import PacketHeader


class FastestLap(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
        ("lapTime", ctypes.c_float),
    ]


class Retirement(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]


class TeamMateInPits(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]


class RaceWinner(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]


class Penalty(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("penaltyType", ctypes.c_uint8),
        ("infringementType", ctypes.c_uint8),
        ("vehicleIdx", ctypes.c_uint8),
        ("otherVehicleIdx", ctypes.c_uint8),
        ("time", ctypes.c_uint8),
        ("lapNum", ctypes.c_uint8),
        ("placesGained", ctypes.c_uint8),
    ]


class SpeedTrap(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
        ("speed", ctypes.c_float),
        ("isOverallFastestInSession", ctypes.c_uint8),
        ("isDriverFastestInSession", ctypes.c_uint8),
        ("fastestVehicleIdxInSession", ctypes.c_uint8),
        ("fastestSpeedInSession", ctypes.c_float),
    ]


class StartLights(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("numLights", ctypes.c_uint8),
    ]


class DriveThroughPenaltyServed(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]


class StopGoPenaltyServed(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]


class Flashback(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("flashbackFrameIdentifier", ctypes.c_uint32),
        ("flashbackSessionTime", ctypes.c_float),
    ]


class Buttons(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_buttonStatus", ctypes.c_uint32),
    ]


class EventDataDetails(ctypes.Union):
    _fields_ = [
        ("FastestLap", FastestLap),
        ("Retirement", Retirement),
        ("TeamMateInPits", TeamMateInPits),
        ("RaceWinner", RaceWinner),
        ("Penalty", Penalty),
        ("SpeedTrap", SpeedTrap),
        ("StartLights", StartLights),
        ("DriveThroughPenaltyServed", DriveThroughPenaltyServed),
        ("StopGoPenaltyServed", StopGoPenaltyServed),
        ("Flashback", Flashback),
        ("Buttons", Buttons),
    ]


EVENT_CODE_MAP = {
    "FTLP": FastestLap,
    "RTMT": Retirement,
    "TMPT": TeamMateInPits,
    "RCWN": RaceWinner,
    "PENA": Penalty,
    "SPTP": SpeedTrap,
    "STLG": StartLights,
    "DTSV": DriveThroughPenaltyServed,
    "SGSV": StopGoPenaltyServed,
    "FLBK": Flashback,
    "BUTN": Buttons,
}


class PacketEventData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_eventStringCode", ctypes.c_uint8 * 4),
        ("m_eventDetails", EventDataDetails),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        return {**header_columns, "m_eventStringCode": str}

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        return {
            **header_row,
            "m_eventStringCode": self.m_eventStringCode.decode("utf-8"),
        }
