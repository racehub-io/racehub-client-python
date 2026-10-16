import ctypes
from .packetheader import PacketHeader

NUM_TYRES_SETS = 20


class TyreSetData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_actualTyreCompound", ctypes.c_uint8),
        ("m_visualTyreCompound", ctypes.c_uint8),
        ("m_wear", ctypes.c_uint8),
        ("m_available", ctypes.c_uint8),
        ("m_recommendedSession", ctypes.c_uint8),
        ("m_lifeSpan", ctypes.c_uint8),
        ("m_usableLife", ctypes.c_uint8),
        ("m_lapDeltaTime", ctypes.c_uint16),
        ("m_fitted", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketTyreSetsData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carIdx", ctypes.c_uint8),
        ("m_tyreSetData", TyreSetData * NUM_TYRES_SETS),
        ("m_fittedIdex", ctypes.c_uint8),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        tyre_set_data_columns = {
            f"m_tyreSetData_{i}_{field_name}": field_type
            for i in range(NUM_TYRES_SETS)
            for field_name, field_type in TyreSetData().columns().items()
        }

        return {
            **header_columns,
            **tyre_set_data_columns,
            "m_carIdx": ctypes.c_uint8,
            "m_fittedIdex": ctypes.c_uint8,
        }

    def row(self, car_index):
        if self.m_carIdx == car_index:
            header_row = {
                f"m_header_{field_name}": value
                for field_name, value in self.m_header.row().items()
            }
            tyre_set_data_row = {
                f"m_tyreSetData_{i}_{field_name}": value
                for i in range(NUM_TYRES_SETS)
                for field_name, value in self.m_tyreSetData[car_index].row().items()
            }
            other_rows = {
                "m_carIdx": self.m_carIdx,
                "m_fittedIdex": self.m_fittedIdex,
            }
        else:
            header_row = {
                f"m_header_{field_name}": value
                for field_name, value in self.m_header.row().items()
            }
            tyre_set_data_row = {
                f"m_tyreSetData_{i}_{field_name}": None
                for i in range(NUM_TYRES_SETS)
                for field_name, _ in TyreSetData().columns().items()
            }
            other_rows = {"m_carIdx": None, "m_fittedIdex": None}
        return {**header_row, **tyre_set_data_row, **other_rows}
