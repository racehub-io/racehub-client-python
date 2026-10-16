import ctypes
from .packetheader import PacketHeader


class CarDamageData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_tyresWearRL", ctypes.c_float),
        ("m_tyresWearRR", ctypes.c_float),
        ("m_tyresWearFL", ctypes.c_float),
        ("m_tyresWearFR", ctypes.c_float),
        ("m_tyresDamageRL", ctypes.c_uint8),
        ("m_tyresDamageRR", ctypes.c_uint8),
        ("m_tyresDamageFL", ctypes.c_uint8),
        ("m_tyresDamageFR", ctypes.c_uint8),
        ("m_brakesDamageRL", ctypes.c_uint8),
        ("m_brakesDamageRR", ctypes.c_uint8),
        ("m_brakesDamageFL", ctypes.c_uint8),
        ("m_brakesDamageFR", ctypes.c_uint8),
        ("m_frontLeftWingDamage", ctypes.c_uint8),
        ("m_frontRightWingDamage", ctypes.c_uint8),
        ("m_rearWingDamage", ctypes.c_uint8),
        ("m_floorDamage", ctypes.c_uint8),
        ("m_diffuserDamage", ctypes.c_uint8),
        ("m_sidepodDamage", ctypes.c_uint8),
        ("m_drsFault", ctypes.c_uint8),
        ("m_ersFault", ctypes.c_uint8),
        ("m_gearBoxDamage", ctypes.c_uint8),
        ("m_engineDamage", ctypes.c_uint8),
        ("m_engineMGUHWear", ctypes.c_uint8),
        ("m_engineESWear", ctypes.c_uint8),
        ("m_engineCEWear", ctypes.c_uint8),
        ("m_engineICEWear", ctypes.c_uint8),
        ("m_engineMGUKWear", ctypes.c_uint8),
        ("m_engineTCWear", ctypes.c_uint8),
        ("m_engineBlown", ctypes.c_uint8),
        ("m_engineSeized", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {field_name: getattr(self, field_name) for field_name, _ in self._fields_}


class PacketCarDamageData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carDamageData", CarDamageData * 22),
    ]

    def columns(self):
        header_columns = {f'm_header_{field_name}': field_type for field_name, field_type in PacketHeader().columns().items()}
        car_damage_data_columns = {f'm_carDamageData_{field_name}': field_type for field_name, field_type in CarDamageData().columns().items()}
        return {**header_columns, **car_damage_data_columns}

    def row(self, car_index):
        header_row = {f'm_header_{field_name}': value for field_name, value in self.m_header.row().items()}
        car_damage_data_row = {f'm_carDamageData_{field_name}': value for field_name, value in self.m_carDamageData[car_index].row().items()}
        return {**header_row, **car_damage_data_row}
