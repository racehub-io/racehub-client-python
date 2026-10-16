import ctypes


class FileHeader(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("rhc_version_major", ctypes.c_uint16),
        ("rhc_version_minor", ctypes.c_uint16),
        ("rhc_version_patch", ctypes.c_uint16),
        ("recorder_type", ctypes.c_uint16),
        ("game_type", ctypes.c_uint16),
        ("recorder_name", ctypes.c_char * 32),
        ("partition", ctypes.c_uint16),
        ("year", ctypes.c_uint16),
        ("month", ctypes.c_uint16),
        ("day", ctypes.c_uint16),
        ("hour", ctypes.c_uint16),
        ("minute", ctypes.c_uint16),
        ("second", ctypes.c_uint16),
        ("millisecond", ctypes.c_uint16),
    ]

    def to_dict(self):
        return {
            field_name: getattr(self, field_name).decode("utf-8").rstrip("\x00")
            if field_name == "recorder_name"
            else getattr(self, field_name)
            for field_name, _ in self._fields_
        }
