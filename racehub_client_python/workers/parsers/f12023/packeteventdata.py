import ctypes
from .packetheader import PacketHeader


class FastestLap(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
        ("lapTime", ctypes.c_float),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class Retirement(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class TeamMateInPits(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class RaceWinner(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


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

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


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

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class StartLights(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("numLights", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class DriveThroughPenaltyServed(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class StopGoPenaltyServed(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("vehicleIdx", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class Flashback(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("flashbackFrameIdentifier", ctypes.c_uint32),
        ("flashbackSessionTime", ctypes.c_float),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class Buttons(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("buttonStatus", ctypes.c_uint32),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class Overtake(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("overtakingVehicleIdx", ctypes.c_uint8),
        ("beingOvertakenVehicleIdx", ctypes.c_uint8),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


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
        ("Overtake", Overtake),
    ]

    def to_dict(self):
        for field_name, _ in self._fields_:
            if getattr(self, field_name) is not None:
                return {field_name: getattr(self, field_name).to_dict()}
        return {}


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
    "OVTK": Overtake,
}


class PacketEventData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_eventStringCode", ctypes.c_uint8 * 4),
        ("m_eventDetails", EventDataDetails),
    ]

    def to_dict(self):
        result = {
            field_name: "".join(map(chr, getattr(self, field_name)))
            if field_name == "m_eventStringCode"
            else getattr(self, field_name).to_dict()
            if isinstance(getattr(self, field_name), ctypes.Structure)
            else getattr(self, field_name)
            for field_name, field_type in self._fields_
            if field_name != "m_eventDetails"
        }

        if result["m_eventStringCode"] in EVENT_CODE_MAP:
            result["m_eventDetails"] = (
                EVENT_CODE_MAP[result["m_eventStringCode"]]
                .from_buffer_copy(self.m_eventDetails)
                .to_dict()
            )
        else:
            result["m_eventDetails"] = {}

        return result

    def flatten(self, car_index):
        packet_dict = self.to_dict()

        # Flatten the header fields
        header_fields = {"m_header_" + k: v for k, v in packet_dict["m_header"].items()}
        del packet_dict["m_header"]

        # Extract car data and other fields
        other_fields = {k: v for k, v in packet_dict.items() if k != "m_eventDetails"}

        # Flatten the car array data fields
        event_data_fields = {
            "m_eventDetails_" + k: v for k, v in packet_dict["m_eventDetails"].items()
        }

        return {
            **header_fields,
            **other_fields,
            **event_data_fields,
        }
