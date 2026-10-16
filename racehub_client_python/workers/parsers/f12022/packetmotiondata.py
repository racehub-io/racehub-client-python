import ctypes
from .packetheader import PacketHeader


class CarMotionData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_worldPositionX", ctypes.c_float),
        ("m_worldPositionY", ctypes.c_float),
        ("m_worldPositionZ", ctypes.c_float),
        ("m_worldVelocityX", ctypes.c_float),
        ("m_worldVelocityY", ctypes.c_float),
        ("m_worldVelocityZ", ctypes.c_float),
        ("m_worldForwardDirX", ctypes.c_int16),
        ("m_worldForwardDirY", ctypes.c_int16),
        ("m_worldForwardDirZ", ctypes.c_int16),
        ("m_worldRightDirX", ctypes.c_int16),
        ("m_worldRightDirY", ctypes.c_int16),
        ("m_worldRightDirZ", ctypes.c_int16),
        ("m_gForceLateral", ctypes.c_float),
        ("m_gForceLongitudinal", ctypes.c_float),
        ("m_gForceVertical", ctypes.c_float),
        ("m_yaw", ctypes.c_float),
        ("m_pitch", ctypes.c_float),
        ("m_roll", ctypes.c_float),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketMotionData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carMotionData", CarMotionData * 22),
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
        ("m_wheelSlipRL", ctypes.c_float),
        ("m_wheelSlipRR", ctypes.c_float),
        ("m_wheelSlipFL", ctypes.c_float),
        ("m_wheelSlipFR", ctypes.c_float),
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
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        car_motion_data_columns = {
            f"m_carMotionData_{field_name}": field_type
            for field_name, field_type in CarMotionData().columns().items()
        }
        additional_fields = {
            "m_suspensionPositionRL": ctypes.c_float,
            "m_suspensionPositionRR": ctypes.c_float,
            "m_suspensionPositionFL": ctypes.c_float,
            "m_suspensionPositionFR": ctypes.c_float,
            "m_suspensionVelocityRL": ctypes.c_float,
            "m_suspensionVelocityRR": ctypes.c_float,
            "m_suspensionVelocityFL": ctypes.c_float,
            "m_suspensionVelocityFR": ctypes.c_float,
            "m_suspensionAccelerationRL": ctypes.c_float,
            "m_suspensionAccelerationRR": ctypes.c_float,
            "m_suspensionAccelerationFL": ctypes.c_float,
            "m_suspensionAccelerationFR": ctypes.c_float,
            "m_wheelSpeedRL": ctypes.c_float,
            "m_wheelSpeedRR": ctypes.c_float,
            "m_wheelSpeedFL": ctypes.c_float,
            "m_wheelSpeedFR": ctypes.c_float,
            "m_wheelSlipRL": ctypes.c_float,
            "m_wheelSlipRR": ctypes.c_float,
            "m_wheelSlipFL": ctypes.c_float,
            "m_wheelSlipFR": ctypes.c_float,
            "m_localVelocityX": ctypes.c_float,
            "m_localVelocityY": ctypes.c_float,
            "m_localVelocityZ": ctypes.c_float,
            "m_angularVelocityX": ctypes.c_float,
            "m_angularVelocityY": ctypes.c_float,
            "m_angularVelocityZ": ctypes.c_float,
            "m_angularAccelerationX": ctypes.c_float,
            "m_angularAccelerationY": ctypes.c_float,
            "m_angularAccelerationZ": ctypes.c_float,
            "m_frontWheelsAngle": ctypes.c_float,
        }
        return {**header_columns, **car_motion_data_columns, **additional_fields}

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        car_motion_data_row = {
            f"m_carMotionData_{field_name}": value
            for field_name, value in self.m_carMotionData[car_index].row().items()
        }

        is_player_index = self.m_header.m_playerCarIndex == car_index

        default_value = None
        additional_fields = {
            "m_suspensionPositionRL": default_value
            if is_player_index
            else self.m_suspensionPositionRL,
            "m_suspensionPositionRR": default_value
            if is_player_index
            else self.m_suspensionPositionRR,
            "m_suspensionPositionFL": default_value
            if is_player_index
            else self.m_suspensionPositionFL,
            "m_suspensionPositionFR": default_value
            if is_player_index
            else self.m_suspensionPositionFR,
            "m_suspensionVelocityRL": default_value
            if is_player_index
            else self.m_suspensionVelocityRL,
            "m_suspensionVelocityRR": default_value
            if is_player_index
            else self.m_suspensionVelocityRR,
            "m_suspensionVelocityFL": default_value
            if is_player_index
            else self.m_suspensionVelocityFL,
            "m_suspensionVelocityFR": default_value
            if is_player_index
            else self.m_suspensionVelocityFR,
            "m_suspensionAccelerationRL": default_value
            if is_player_index
            else self.m_suspensionAccelerationRL,
            "m_suspensionAccelerationRR": default_value
            if is_player_index
            else self.m_suspensionAccelerationRR,
            "m_suspensionAccelerationFL": default_value
            if is_player_index
            else self.m_suspensionAccelerationFL,
            "m_suspensionAccelerationFR": default_value
            if is_player_index
            else self.m_suspensionAccelerationFR,
            "m_wheelSpeedRL": default_value if is_player_index else self.m_wheelSpeedRL,
            "m_wheelSpeedRR": default_value if is_player_index else self.m_wheelSpeedRR,
            "m_wheelSpeedFL": default_value if is_player_index else self.m_wheelSpeedFL,
            "m_wheelSpeedFR": default_value if is_player_index else self.m_wheelSpeedFR,
            "m_wheelSlipRL": default_value if is_player_index else self.m_wheelSlipRL,
            "m_wheelSlipRR": default_value if is_player_index else self.m_wheelSlipRR,
            "m_wheelSlipFL": default_value if is_player_index else self.m_wheelSlipFL,
            "m_wheelSlipFR": default_value if is_player_index else self.m_wheelSlipFR,
            "m_wheelSlipRL": default_value if is_player_index else self.m_wheelSlipRL,
            "m_wheelSlipRR": default_value if is_player_index else self.m_wheelSlipRR,
            "m_localVelocityX": default_value
            if is_player_index
            else self.m_localVelocityX,
            "m_localVelocityY": default_value
            if is_player_index
            else self.m_localVelocityY,
            "m_localVelocityZ": default_value
            if is_player_index
            else self.m_localVelocityZ,
            "m_angularVelocityX": default_value
            if is_player_index
            else self.m_angularVelocityX,
            "m_angularVelocityY": default_value
            if is_player_index
            else self.m_angularVelocityY,
            "m_angularVelocityZ": default_value
            if is_player_index
            else self.m_angularVelocityZ,
            "m_angularAccelerationX": default_value
            if is_player_index
            else self.m_angularAccelerationX,
            "m_angularAccelerationY": default_value
            if is_player_index
            else self.m_angularAccelerationY,
            "m_angularAccelerationZ": default_value
            if is_player_index
            else self.m_angularAccelerationZ,
            "m_frontWheelsAngle": default_value
            if is_player_index
            else self.m_frontWheelsAngle,
        }

        return {**header_row, **car_motion_data_row, **additional_fields}
