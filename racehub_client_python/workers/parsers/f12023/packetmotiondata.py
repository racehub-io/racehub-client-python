import ctypes
from .packetheader import PacketHeader


class CarMotionData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_worldPositionX", ctypes.c_float),
        ("m_worldPositionY", ctypes.c_float),
        ("m_worldPositionZ", ctypes.c_float),
        ("m_worldVelocityX", ctypes.c_float),
        ("m_worldVelocityY", ctypes.c_float),
        ("m_worldVelocityZ", ctypes.c_float),
        ("m_worldForwardDirX", ctypes.c_int16),
        ("m_worldForwardDirY", ctypes.c_int16),
        ("m_worldForwardDirZ", ctypes.c_int16),
        ("m_worldRightDirX", ctypes.c_int16),
        ("m_worldRightDirY", ctypes.c_int16),
        ("m_worldRightDirZ", ctypes.c_int16),
        ("m_gForceLateral", ctypes.c_float),
        ("m_gForceLongitudinal", ctypes.c_float),
        ("m_gForceVertical", ctypes.c_float),
        ("m_yaw", ctypes.c_float),
        ("m_pitch", ctypes.c_float),
        ("m_roll", ctypes.c_float),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketMotionData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carMotionData", CarMotionData * 22),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        car_motion_data_columns = {
            f"m_carMotionData_{field_name}": field_type
            for field_name, field_type in CarMotionData().columns().items()
        }
        return {**header_columns, **car_motion_data_columns}

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        car_motion_data_row = {
            f"m_carMotionData_{field_name}": value
            for field_name, value in self.m_carMotionData[car_index].row().items()
        }
        return {**header_row, **car_motion_data_row}
