import ctypes

from .packetheader import PacketHeader


class FinalClassificationData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_position", ctypes.c_uint8),
        ("m_numLaps", ctypes.c_uint8),
        ("m_gridPosition", ctypes.c_uint8),
        ("m_points", ctypes.c_uint8),
        ("m_numPitStops", ctypes.c_uint8),
        ("m_resultStatus", ctypes.c_uint8),
        ("m_bestLapTimeInMS", ctypes.c_uint32),
        ("m_totalRaceTime", ctypes.c_double),
        ("m_penaltiesTime", ctypes.c_uint8),
        ("m_numPenalties", ctypes.c_uint8),
        ("m_numTyreStints", ctypes.c_uint8),
        ("m_tyreStintsActual", ctypes.c_uint8 * 8),
        ("m_tyreStintsVisual", ctypes.c_uint8 * 8),
        ("m_tyreStintsEndLaps", ctypes.c_uint8 * 8),
    ]

    def columns(self):
        columns = {}
        for field_name, field_type in self._fields_:
            if field_name in [
                "m_tyreStintsActual",
                "m_tyreStintsVisual",
                "m_tyreStintsEndLaps",
            ]:
                for i in range(8):
                    columns[f"{field_name}_lap{i+1}"] = ctypes.c_uint8
            else:
                columns[field_name] = field_type
        return columns

    def row(self):
        row = {}
        for field_name, _ in self._fields_:
            if field_name in [
                "m_tyreStintsActual",
                "m_tyreStintsVisual",
                "m_tyreStintsEndLaps",
            ]:
                for i, value in enumerate(getattr(self, field_name)):
                    row[f"{field_name}_lap{i+1}"] = value
            else:
                row[field_name] = getattr(self, field_name)
        return row


class PacketFinalClassificationData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_numCars", ctypes.c_uint8),
        ("m_classificationData", FinalClassificationData * 22),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        classification_data_columns = {
            f"m_classificationData_{field_name}": field_type
            for field_name, field_type in FinalClassificationData().columns().items()
        }
        other_columns = {
            field_name: field_type
            for field_name, field_type in self._fields_
            if field_name not in ["m_header", "m_classificationData"]
        }

        return {**header_columns, **classification_data_columns, **other_columns}

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        classification_data_row = {
            f"m_classificationData_{field_name}": value
            for field_name, value in self.m_classificationData[car_index].row().items()
        }
        other_rows = {
            field_name: getattr(self, field_name)
            for field_name, _ in self._fields_
            if field_name not in ["m_header", "m_classificationData"]
        }
        return {**header_row, **classification_data_row, **other_rows}
