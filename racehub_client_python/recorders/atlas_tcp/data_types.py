class ByteOrderType:
    BIG_ENDIAN = "BigEndian"
    LITTLE_ENDIAN = "LittleEndian"


class ConversionType:
    RATIONAL = "rational"
    TEXT = "text"
    FORMULA = "formula"


class DataSource:
    PERIODIC = "Periodic"


class DataType:
    PACKED = "Packed"
    CHAR = "Char"
    SHORT = "Short"
    INT = "Int"
    LLONG = "LLong"
    FLOAT = "Float"
    DOUBLE = "Double"
    USHORT = "UShort"
    UINT = "UInt"
    TRIPLEFLOAT = "TripleFloat"


class TriggerSource:
    PITSTRAIGHT = 0
    PITLANE = 1
    DEFAULT = 2
    START = 3
    END = 4
    UNKNOWN = 5


class PacketFieldType:
    CHAR = "Char"
    SIGNED_CHAR = "SignedChar"
    INT8 = "Int8"
    SBYTE = "SByte"

    PACKED = "Packed"
    UNSIGNED_CHAR = "UnsignedChar"
    UINT8 = "UInt8"
    BYTE = "Byte"

    SHORT = "Short"
    SIGNED_SHORT = "SignedShort"
    INT16 = "Int16"

    USHORT = "UShort"
    UNSIGNED_SHORT = "UnsignedShort"
    UINT16 = "UInt16"
    WORD = "Word"

    INT = "Int"
    SIGNED_INT = "SignedInt"
    INT32 = "Int32"
    LLONG = "LLong"

    UINT = "UInt"
    UNSIGNED_INT = "UnsignedInt"
    UINT32 = "UInt32"
    DWORD = "DWord"

    FLOAT = "Float"
    SINGLE = "Single"
    TRIPLEFLOAT = "TripleFloat"

    DOUBLE = "Double"
    STRING = "String"


def packet_field_type_to_data_type(field_type: str) -> str:
    if field_type in (
        PacketFieldType.CHAR,
        PacketFieldType.SIGNED_CHAR,
        PacketFieldType.INT8,
        PacketFieldType.SBYTE,
    ):
        return DataType.CHAR
    elif field_type in (
        PacketFieldType.PACKED,
        PacketFieldType.UNSIGNED_CHAR,
        PacketFieldType.UINT8,
        PacketFieldType.BYTE,
    ):
        return DataType.PACKED
    elif field_type in (
        PacketFieldType.SHORT,
        PacketFieldType.SIGNED_SHORT,
        PacketFieldType.INT16,
    ):
        return DataType.SHORT
    elif field_type in (
        PacketFieldType.USHORT,
        PacketFieldType.UNSIGNED_SHORT,
        PacketFieldType.UINT16,
        PacketFieldType.WORD,
    ):
        return DataType.USHORT
    elif field_type in (
        PacketFieldType.INT,
        PacketFieldType.SIGNED_INT,
        PacketFieldType.INT32,
    ):
        return DataType.INT
    elif field_type == PacketFieldType.LLONG:
        return DataType.LLONG
    elif field_type in (
        PacketFieldType.UINT,
        PacketFieldType.UNSIGNED_INT,
        PacketFieldType.UINT32,
        PacketFieldType.DWORD,
    ):
        return DataType.UINT
    elif field_type in (PacketFieldType.FLOAT, PacketFieldType.SINGLE):
        return DataType.FLOAT
    elif field_type == PacketFieldType.TRIPLEFLOAT:
        return DataType.TRIPLEFLOAT
    elif field_type == PacketFieldType.DOUBLE:
        return DataType.DOUBLE
    elif field_type == PacketFieldType.STRING:
        return DataType.CHAR  # or some fallback
    else:
        raise ValueError(f"Unknown PacketFieldType: {field_type}")


def default_data_type_format(dt: str) -> str:
    if dt in [
        DataType.CHAR,
        DataType.PACKED,
        DataType.SHORT,
        DataType.USHORT,
        DataType.INT,
        DataType.LLONG,
        DataType.UINT,
    ]:
        return "%d"
    elif dt in [DataType.FLOAT, DataType.TRIPLEFLOAT]:
        return "%.5f"
    elif dt == DataType.DOUBLE:
        return "%.8f"
    else:
        raise ValueError(f"Unknown DataType: {dt}")


def data_type_min_value(dt: str) -> float:
    if dt == DataType.CHAR:
        return -128
    if dt == DataType.PACKED:
        return 0
    if dt == DataType.SHORT:
        return -32768
    if dt == DataType.USHORT:
        return 0
    if dt == DataType.INT:
        return -2147483648
    if dt == DataType.LLONG:
        return -2147483648
    if dt == DataType.UINT:
        return 0
    if dt in (DataType.FLOAT, DataType.TRIPLEFLOAT):
        return -3.4e38
    if dt == DataType.DOUBLE:
        return -1.7e308
    return 0.0


def data_type_max_value(dt: str) -> float:
    if dt == DataType.CHAR:
        return 127
    if dt == DataType.PACKED:
        return 255
    if dt == DataType.SHORT:
        return 32767
    if dt == DataType.USHORT:
        return 65535
    if dt == DataType.INT:
        return 2147483647
    if dt == DataType.LLONG:
        return 2147483647
    if dt == DataType.UINT:
        return 4294967295
    if dt in (DataType.FLOAT, DataType.TRIPLEFLOAT):
        return 3.4e38
    if dt == DataType.DOUBLE:
        return 1.7e308
    return 1.0


def get_packet_field_size(field_type: str) -> int:
    if field_type in (
        PacketFieldType.CHAR,
        PacketFieldType.SIGNED_CHAR,
        PacketFieldType.INT8,
        PacketFieldType.SBYTE,
        PacketFieldType.PACKED,
        PacketFieldType.UNSIGNED_CHAR,
        PacketFieldType.UINT8,
        PacketFieldType.BYTE,
    ):
        return 1
    elif field_type in (
        PacketFieldType.SHORT,
        PacketFieldType.SIGNED_SHORT,
        PacketFieldType.INT16,
        PacketFieldType.USHORT,
        PacketFieldType.UNSIGNED_SHORT,
        PacketFieldType.UINT16,
        PacketFieldType.WORD,
    ):
        return 2
    elif field_type in (
        PacketFieldType.INT,
        PacketFieldType.SIGNED_INT,
        PacketFieldType.INT32,
        PacketFieldType.LLONG,
        PacketFieldType.UINT,
        PacketFieldType.UNSIGNED_INT,
        PacketFieldType.UINT32,
        PacketFieldType.DWORD,
        PacketFieldType.FLOAT,
        PacketFieldType.SINGLE,
        PacketFieldType.TRIPLEFLOAT,
    ):
        return 4
    elif field_type == PacketFieldType.DOUBLE:
        return 8
    elif field_type == PacketFieldType.STRING:
        return 1  # or variable
    else:
        raise ValueError(f"Unknown field type {field_type}")
