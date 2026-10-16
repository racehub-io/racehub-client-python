import ctypes
from .packetheader import PacketHeader


class CarSetupData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_frontWing", ctypes.c_uint8),
        ("m_rearWing", ctypes.c_uint8),
        ("m_onThrottle", ctypes.c_uint8),
        ("m_offThrottle", ctypes.c_uint8),
        ("m_frontCamber", ctypes.c_float),
        ("m_rearCamber", ctypes.c_float),
        ("m_frontToe", ctypes.c_float),
        ("m_rearToe", ctypes.c_float),
        ("m_frontSuspension", ctypes.c_uint8),
        ("m_rearSuspension", ctypes.c_uint8),
        ("m_frontAntiRollBar", ctypes.c_uint8),
        ("m_rearAntiRollBar", ctypes.c_uint8),
        ("m_frontSuspensionHeight", ctypes.c_uint8),
        ("m_rearSuspensionHeight", ctypes.c_uint8),
        ("m_brakePressure", ctypes.c_uint8),
        ("m_brakeBias", ctypes.c_uint8),
        ("m_rearLeftTyrePressure", ctypes.c_float),
        ("m_rearRightTyrePressure", ctypes.c_float),
        ("m_frontLeftTyrePressure", ctypes.c_float),
        ("m_frontRightTyrePressure", ctypes.c_float),
        ("m_ballast", ctypes.c_uint8),
        ("m_fuelLoad", ctypes.c_float),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {field_name: getattr(self, field_name) for field_name, _ in self._fields_}


class PacketCarSetupData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [("m_header", PacketHeader), ("m_carSetupData", CarSetupData * 22)]

    def columns(self):
        header_columns = {f'm_header_{field_name}': field_type for field_name, field_type in PacketHeader().columns().items()}
        car_setup_data_columns = {f'm_carSetupData_{field_name}': field_type for field_name, field_type in CarSetupData().columns().items()}
        return {**header_columns, **car_setup_data_columns}

    def row(self, car_index):
        header_row = {f'm_header_{field_name}': value for field_name, value in self.m_header.row().items()}
        car_setup_data_row = {f'm_carSetupData_{field_name}': value for field_name, value in self.m_carSetupData[car_index].row().items()}
        return {**header_row, **car_setup_data_row}
