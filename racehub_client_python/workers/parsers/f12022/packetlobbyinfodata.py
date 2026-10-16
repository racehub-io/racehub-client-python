import ctypes

from .packetheader import PacketHeader


class LobbyInfoData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_aiControlled", ctypes.c_uint8),
        ("m_teamId", ctypes.c_uint8),
        ("m_nationality", ctypes.c_uint8),
        ("m_name", ctypes.c_char * 48),
        ("m_carNumber", ctypes.c_uint8),
        ("m_readyStatus", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {field_name: getattr(self, field_name).decode('utf-8') if field_name == 'm_name' else getattr(self, field_name) for field_name, _ in self._fields_}



class PacketLobbyInfoData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_numPlayers", ctypes.c_uint8),
        ("m_lobbyPlayers", LobbyInfoData * 22),
    ]

    def columns(self):
        header_columns = {f'm_header_{field_name}': field_type for field_name, field_type in PacketHeader().columns().items()}
        lobby_players_columns = {f'm_lobbyPlayers_{field_name}': field_type for field_name, field_type in LobbyInfoData().columns().items()}
        return {**header_columns, **lobby_players_columns, 'm_numPlayers': ctypes.c_uint8}

    def row(self, player_index):
        header_row = {f'm_header_{field_name}': value for field_name, value in self.m_header.row().items()}
        lobby_players_row = {f'm_lobbyPlayers_{field_name}': value for field_name, value in self.m_lobbyPlayers[player_index].row().items()}
        return {**header_row, **lobby_players_row, 'm_numPlayers': self.m_numPlayers}
