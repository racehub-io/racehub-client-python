import ctypes

from .packetheader import PacketHeader

NUM_HISTORIC_LAPS = 100
NUM_TYRE_STINTS = 8


class LapHistoryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_lapTimeInMS", ctypes.c_uint32),
        ("m_sector1TimeMSPart", ctypes.c_uint16),
        ("m_sector1TimeMinutesPart", ctypes.c_uint8),
        ("m_sector2TimeMSPart", ctypes.c_uint16),
        ("m_sector2TimeMinutesPart", ctypes.c_uint8),
        ("m_sector3TimeMSPart", ctypes.c_uint16),
        ("m_sector3TimeMinutesPart", ctypes.c_uint8),
        ("m_lapValidBitFlags", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class TyreStintHistoryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_endLap", ctypes.c_uint8),
        ("m_tyreActualCompound", ctypes.c_uint8),
        ("m_tyreVisualCompound", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketSessionHistoryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carIdx", ctypes.c_uint8),
        ("m_numLaps", ctypes.c_uint8),
        ("m_numTyreStints", ctypes.c_uint8),
        ("m_bestLapTimeLapNum", ctypes.c_uint8),
        ("m_bestSector1LapNum", ctypes.c_uint8),
        ("m_bestSector2LapNum", ctypes.c_uint8),
        ("m_bestSector3LapNum", ctypes.c_uint8),
        ("m_lapHistoryData", LapHistoryData * NUM_HISTORIC_LAPS),
        ("m_tyreStintsHistoryData", TyreStintHistoryData * NUM_TYRE_STINTS),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        lap_history_data_columns = {
            f"m_lapHistoryData_{i}_{field_name}": field_type
            for i in range(NUM_HISTORIC_LAPS)
            for field_name, field_type in LapHistoryData().columns().items()
        }
        tyre_stints_history_data_columns = {
            f"m_tyreStintsHistoryData_{i}_{field_name}": field_type
            for i in range(NUM_TYRE_STINTS)
            for field_name, field_type in TyreStintHistoryData().columns().items()
        }
        other_columns = {
            field_name: field_type
            for field_name, field_type in self._fields_
            if field_name
            not in ["m_header", "m_lapHistoryData", "m_tyreStintsHistoryData"]
        }

        return {
            **header_columns,
            **lap_history_data_columns,
            **tyre_stints_history_data_columns,
            **other_columns,
        }

    def row(self, player_index):
        if self.m_carIdx == player_index:
            header_row = {
                f"m_header_{field_name}": value
                for field_name, value in self.m_header.row().items()
            }
            lap_history_data_rows = {
                f"m_lapHistoryData_{i}_{field_name}": value
                for i in range(NUM_HISTORIC_LAPS)
                for field_name, value in self.m_lapHistoryData[i].row().items()
            }
            tyre_stints_history_data_rows = {
                f"m_tyreStintsHistoryData_{i}_{field_name}": value
                for i in range(NUM_TYRE_STINTS)
                for field_name, value in self.m_tyreStintsHistoryData[i].row().items()
            }
            other_rows = {
                field_name: getattr(self, field_name)
                for field_name, _ in self._fields_
                if field_name
                not in ["m_header", "m_lapHistoryData", "m_tyreStintsHistoryData"]
            }
        else:
            header_row = {
                f"m_header_{field_name}": value
                for field_name, value in self.m_header.row().items()
            }
            lap_history_data_rows = {
                f"m_lapHistoryData_{i}_{field_name}": None
                for i in range(NUM_HISTORIC_LAPS)
                for field_name, _ in LapHistoryData().columns().items()
            }
            tyre_stints_history_data_rows = {
                f"m_tyreStintsHistoryData_{i}_{field_name}": None
                for i in range(NUM_TYRE_STINTS)
                for field_name, _ in TyreStintHistoryData().columns().items()
            }
            other_rows = {
                field_name: None
                for field_name, _ in self._fields_
                if field_name
                not in ["m_header", "m_lapHistoryData", "m_tyreStintsHistoryData"]
            }

        return {
            **header_row,
            **lap_history_data_rows,
            **tyre_stints_history_data_rows,
            **other_rows,
        }
