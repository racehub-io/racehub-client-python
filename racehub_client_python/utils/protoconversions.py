import pyarrow as pa
from google.protobuf.descriptor import FieldDescriptor

PROTO_TO_PYARROW_MAP = {
    FieldDescriptor.TYPE_DOUBLE: pa.float64(),
    FieldDescriptor.TYPE_FLOAT: pa.float32(),
    FieldDescriptor.TYPE_INT64: pa.int64(),
    FieldDescriptor.TYPE_UINT64: pa.uint64(),
    FieldDescriptor.TYPE_INT32: pa.int32(),
    FieldDescriptor.TYPE_FIXED64: pa.uint64(),
    FieldDescriptor.TYPE_FIXED32: pa.uint32(),
    FieldDescriptor.TYPE_BOOL: pa.bool_(),
    FieldDescriptor.TYPE_STRING: pa.string(),
    FieldDescriptor.TYPE_BYTES: pa.binary(),
    FieldDescriptor.TYPE_UINT32: pa.uint32(),
    FieldDescriptor.TYPE_ENUM: pa.int32(),
    FieldDescriptor.TYPE_SFIXED32: pa.int32(),
    FieldDescriptor.TYPE_SFIXED64: pa.int64(),
    FieldDescriptor.TYPE_SINT32: pa.int32(),
    FieldDescriptor.TYPE_SINT64: pa.int64(),
}
