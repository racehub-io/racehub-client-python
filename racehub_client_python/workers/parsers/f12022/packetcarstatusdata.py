import ctypes
from .packetheader import PacketHeader


class CarStatusData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_tractionControl", ctypes.c_uint8),
        ("m_antiLockBrakes", ctypes.c_uint8),
        ("m_fuelMix", ctypes.c_uint8),
        ("m_frontBrakeBias", ctypes.c_uint8),
        ("m_pitLimiterStatus", ctypes.c_uint8),
        ("m_fuelInTank", ctypes.c_float),
        ("m_fuelCapacity", ctypes.c_float),
        ("m_fuelRemainingLaps", ctypes.c_float),
        ("m_maxRPM", ctypes.c_uint16),
        ("m_idleRPM", ctypes.c_uint16),
        ("m_maxGears", ctypes.c_uint8),
        ("m_DRSAllowed", ctypes.c_uint8),
        ("m_DRSActivationDistance", ctypes.c_uint16),
        ("m_actualTyreCompound", ctypes.c_uint8),
        ("m_visualTyreCompound", ctypes.c_uint8),
        ("m_tyreAgeLaps", ctypes.c_uint8),
        ("m_vehicleFiaFlags", ctypes.c_int8),
        ("m_ersStoreEnergy", ctypes.c_float),
        ("m_ersDeployMode", ctypes.c_uint8),
        ("m_ersHarvestedThisLapMGUK", ctypes.c_float),
        ("m_ersHarvestedThisLapMGUH", ctypes.c_float),
        ("m_ersDeployedThisLap", ctypes.c_float),
        ("m_networkPaused", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {field_name: getattr(self, field_name) for field_name, _ in self._fields_}


class PacketCarStatusData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carStatusData", CarStatusData * 22),
    ]

    def columns(self):
        header_columns = {f'm_header_{field_name}': field_type for field_name, field_type in PacketHeader().columns().items()}
        car_status_data_columns = {f'm_carStatusData_{field_name}': field_type for field_name, field_type in CarStatusData().columns().items()}
        return {**header_columns, **car_status_data_columns}

    def row(self, car_index):
        header_row = {f'm_header_{field_name}': value for field_name, value in self.m_header.row().items()}
        car_status_data_row = {f'm_carStatusData_{field_name}': value for field_name, value in self.m_carStatusData[car_index].row().items()}
        return {**header_row, **car_status_data_row}

