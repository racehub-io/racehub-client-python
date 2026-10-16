import ctypes


class PacketHeader(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_packetFormat", ctypes.c_uint16),
        ("m_gameMajorVersion", ctypes.c_uint8),
        ("m_gameMinorVersion", ctypes.c_uint8),
        ("m_packetVersion", ctypes.c_uint8),
        ("m_packetId", ctypes.c_uint8),
        ("m_sessionUID", ctypes.c_uint64),
        ("m_sessionTime", ctypes.c_float),
        ("m_frameIdentifier", ctypes.c_uint32),
        ("m_playerCarIndex", ctypes.c_uint8),
        ("m_secondaryPlayerCarIndex", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }
