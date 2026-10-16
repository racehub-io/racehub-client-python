import ctypes
from .packetheader import PacketHeader


class TimeTrialDataSet(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_carIdx", ctypes.c_uint8),
        ("m_teamId", ctypes.c_uint8),
        ("m_lapTimeInMS", ctypes.c_uint32),
        ("m_sector1TimeInMS", ctypes.c_uint32),
        ("m_sector2TimeInMS", ctypes.c_uint32),
        ("m_sector3TimeInMS", ctypes.c_uint32),
        ("m_tractionControl", ctypes.c_uint8),
        ("m_gearboxAssist", ctypes.c_uint8),
        ("m_antiLockBrakes", ctypes.c_uint8),
        ("m_equalCarPerformance", ctypes.c_uint8),
        ("m_customSetup", ctypes.c_uint8),
        ("m_valid", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketTimeTrialData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_playerSessionBestDataSet", TimeTrialDataSet),
        ("m_personalBestDataSet", TimeTrialDataSet),
        ("m_rivalDataSet", TimeTrialDataSet),
    ]

    def _generate_columns(self, prefix, data_set):
        return {
            f"{prefix}_{field_name}": field_type
            for field_name, field_type in data_set.columns().items()
        }

    def _generate_row(self, prefix, data_set):
        return {
            f"{prefix}_{field_name}": value
            for field_name, value in data_set.row().items()
        }

    def columns(self):
        return {
            **self._generate_columns("m_header", PacketHeader()),
            **self._generate_columns("m_playerSessionBestDataSet", TimeTrialDataSet()),
            **self._generate_columns("m_personalBestDataSet", TimeTrialDataSet()),
            **self._generate_columns("m_rivalDataSet", TimeTrialDataSet()),
        }

    def row(self):
        return {
            **self._generate_row("m_header", self.m_header),
            **self._generate_row(
                "m_playerSessionBestDataSet", self.m_playerSessionBestDataSet
            ),
            **self._generate_row("m_personalBestDataSet", self.m_personalBestDataSet),
            **self._generate_row("m_rivalDataSet", self.m_rivalDataSet),
        }
