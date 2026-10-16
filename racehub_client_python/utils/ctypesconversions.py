import ctypes

import numpy as np
import pandas as pd

import pyarrow as pa

CTYPES_TO_PANDAS_MAP = {
    ctypes.c_int8: pd.Int8Dtype(),
    ctypes.c_int16: pd.Int16Dtype(),
    ctypes.c_int32: pd.Int32Dtype(),
    ctypes.c_int64: pd.Int64Dtype(),
    ctypes.c_uint8: pd.UInt8Dtype(),
    ctypes.c_uint16: pd.UInt16Dtype(),
    ctypes.c_uint32: pd.UInt32Dtype(),
    ctypes.c_uint64: pd.UInt64Dtype(),
    ctypes.c_float: np.dtype("float32"),
    ctypes.c_double: np.dtype("float64"),
    ctypes.c_char: np.dtype("str"),
    ctypes.c_bool: np.dtype("bool"),
    ctypes.c_short: pd.Int16Dtype(),
    ctypes.c_long: pd.Int32Dtype(),
    ctypes.c_ulong: pd.UInt32Dtype(),
    ctypes.c_char_p: np.dtype("str"),
    ctypes.c_wchar_p: np.dtype("str"),
}

CTYPES_TO_PYARROW_MAP = {
    ctypes.c_int8: pa.int8(),
    ctypes.c_int16: pa.int16(),
    ctypes.c_int32: pa.int32(),
    ctypes.c_int64: pa.int64(),
    ctypes.c_uint8: pa.uint8(),
    ctypes.c_uint16: pa.uint16(),
    ctypes.c_uint32: pa.uint32(),
    ctypes.c_uint64: pa.uint64(),
    ctypes.c_float: pa.float32(),
    ctypes.c_double: pa.float64(),
    ctypes.c_char: pa.string(),
    ctypes.c_bool: pa.bool_(),
    ctypes.c_short: pa.int16(),
    ctypes.c_long: pa.int64(),  # Note: c_long is platform-dependent, int64() may not be the correct mapping on every platform
    ctypes.c_ulong: pa.uint64(),  # Note: c_ulong is platform-dependent, uint64() may not be the correct mapping on every platform
    ctypes.c_char_p: pa.string(),
    ctypes.c_wchar_p: pa.string(),
    # Add more mappings as required
}
