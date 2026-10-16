import ctypes
from .packetheader import PacketHeader


class ParticipantsData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_aiControlled", ctypes.c_uint8),
        ("m_driverId", ctypes.c_uint8),
        ("m_networkId", ctypes.c_uint8),
        ("m_teamId", ctypes.c_uint8),
        ("m_myTeam", ctypes.c_uint8),
        ("m_raceNumber", ctypes.c_uint8),
        ("m_nationality", ctypes.c_uint8),
        ("m_name", ctypes.c_char * 48),
        ("m_yourTelemetry", ctypes.c_uint8),
        ("m_showOnlineNames", ctypes.c_uint8),
        ("m_techLevel", ctypes.c_uint16),
        ("m_platform", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: (
                getattr(self, field_name).decode("utf-8")
                if field_name == "m_name"
                else getattr(self, field_name)
            )
            for field_name, _ in self._fields_
        }


class PacketParticipantsData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_numActiveCars", ctypes.c_uint8),
        ("m_participantsData", ParticipantsData * 22),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        participants_data_columns = {
            f"m_participantsData_{field_name}": field_type
            for field_name, field_type in ParticipantsData().columns().items()
        }
        num_active_cars_column = {"m_numActiveCars": ctypes.c_uint8}
        return {**header_columns, **num_active_cars_column, **participants_data_columns}

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        participants_data_row = {
            f"m_participantsData_{field_name}": value
            for field_name, value in self.m_participantsData[car_index].row().items()
        }
        num_active_cars_row = {"m_numActiveCars": self.m_numActiveCars}
        return {**header_row, **num_active_cars_row, **participants_data_row}
