import ctypes
from .packetheader import PacketHeader


class PacketMotionExData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_suspensionPositionRL", ctypes.c_float),
        ("m_suspensionPositionRR", ctypes.c_float),
        ("m_suspensionPositionFL", ctypes.c_float),
        ("m_suspensionPositionFR", ctypes.c_float),
        ("m_suspensionVelocityRL", ctypes.c_float),
        ("m_suspensionVelocityRR", ctypes.c_float),
        ("m_suspensionVelocityFL", ctypes.c_float),
        ("m_suspensionVelocityFR", ctypes.c_float),
        ("m_suspensionAccelerationRL", ctypes.c_float),
        ("m_suspensionAccelerationRR", ctypes.c_float),
        ("m_suspensionAccelerationFL", ctypes.c_float),
        ("m_suspensionAccelerationFR", ctypes.c_float),
        ("m_wheelSpeedRL", ctypes.c_float),
        ("m_wheelSpeedRR", ctypes.c_float),
        ("m_wheelSpeedFL", ctypes.c_float),
        ("m_wheelSpeedFR", ctypes.c_float),
        ("m_wheelSlipRatioRL", ctypes.c_float),
        ("m_wheelSlipRatioRR", ctypes.c_float),
        ("m_wheelSlipRatioFL", ctypes.c_float),
        ("m_wheelSlipRatioFR", ctypes.c_float),
        ("m_wheelSlipAngleRL", ctypes.c_float),
        ("m_wheelSlipAngleRR", ctypes.c_float),
        ("m_wheelSlipAngleFL", ctypes.c_float),
        ("m_wheelSlipAngleFR", ctypes.c_float),
        ("m_wheelLatForceRL", ctypes.c_float),
        ("m_wheelLatForceRR", ctypes.c_float),
        ("m_wheelLatForceFL", ctypes.c_float),
        ("m_wheelLatForceFR", ctypes.c_float),
        ("m_wheelLongForceRL", ctypes.c_float),
        ("m_wheelLongForceRR", ctypes.c_float),
        ("m_wheelLongForceFL", ctypes.c_float),
        ("m_wheelLongForceFR", ctypes.c_float),
        ("m_heightOfCOGAboveGround", ctypes.c_float),
        ("m_localVelocityX", ctypes.c_float),
        ("m_localVelocityY", ctypes.c_float),
        ("m_localVelocityZ", ctypes.c_float),
        ("m_angularVelocityX", ctypes.c_float),
        ("m_angularVelocityY", ctypes.c_float),
        ("m_angularVelocityZ", ctypes.c_float),
        ("m_angularAccelerationX", ctypes.c_float),
        ("m_angularAccelerationY", ctypes.c_float),
        ("m_angularAccelerationZ", ctypes.c_float),
        ("m_frontWheelsAngle", ctypes.c_float),
        ("m_wheelVertForceRL", ctypes.c_float),
        ("m_wheelVertForceRR", ctypes.c_float),
        ("m_wheelVertForceFL", ctypes.c_float),
        ("m_wheelVertForceFR", ctypes.c_float),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        other_columns = {
            field_name: field_type
            for field_name, field_type in self._fields_
            if field_name not in ["m_header"]
        }
        return {**header_columns, **other_columns}

    def row(self, player_index):
        if self.m_header.m_playerCarIndex == player_index:
            header_row = {
                f"m_header_{field_name}": value
                for field_name, value in self.m_header.row().items()
            }
            other_rows = {
                field_name: getattr(self, field_name)
                for field_name, _ in self._fields_
                if field_name not in ["m_header"]
            }
        else:
            header_row = {
                f"m_header_{field_name}": value
                for field_name, value in self.m_header.row().items()
            }
            other_rows = {
                field_name: None
                for field_name, _ in self._fields_
                if field_name not in ["m_header"]
            }

        return {
            **header_row,
            **other_rows,
        }
