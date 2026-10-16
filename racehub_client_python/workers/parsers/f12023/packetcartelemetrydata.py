import ctypes
from .packetheader import PacketHeader


class CarTelemetryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_speed", ctypes.c_uint16),
        ("m_throttle", ctypes.c_float),
        ("m_steer", ctypes.c_float),
        ("m_brake", ctypes.c_float),
        ("m_clutch", ctypes.c_uint8),
        ("m_gear", ctypes.c_int8),
        ("m_engineRPM", ctypes.c_uint16),
        ("m_drs", ctypes.c_uint8),
        ("m_revLightsPercent", ctypes.c_uint8),
        ("m_revLightBitValue", ctypes.c_uint16),
        ("m_brakesTemperatureRL", ctypes.c_uint16),
        ("m_brakesTemperatureRR", ctypes.c_uint16),
        ("m_brakesTemperatureFL", ctypes.c_uint16),
        ("m_brakesTemperatureFR", ctypes.c_uint16),
        ("m_tyresSurfaceTemperatureRL", ctypes.c_uint8),
        ("m_tyresSurfaceTemperatureRR", ctypes.c_uint8),
        ("m_tyresSurfaceTemperatureFL", ctypes.c_uint8),
        ("m_tyresSurfaceTemperatureFR", ctypes.c_uint8),
        ("m_tyresInnerTemperatureRL", ctypes.c_uint8),
        ("m_tyresInnerTemperatureRR", ctypes.c_uint8),
        ("m_tyresInnerTemperatureFL", ctypes.c_uint8),
        ("m_tyresInnerTemperatureFR", ctypes.c_uint8),
        ("m_engineTemperature", ctypes.c_uint16),
        ("m_tyresPressureRL", ctypes.c_float),
        ("m_tyresPressureRR", ctypes.c_float),
        ("m_tyresPressureFL", ctypes.c_float),
        ("m_tyresPressureFR", ctypes.c_float),
        ("m_surfaceTypeRL", ctypes.c_uint8),
        ("m_surfaceTypeRR", ctypes.c_uint8),
        ("m_surfaceTypeFL", ctypes.c_uint8),
        ("m_surfaceTypeFR", ctypes.c_uint8),
    ]

    def columns(self):
        return {field_name: field_type for field_name, field_type in self._fields_}

    def row(self):
        return {
            field_name: getattr(self, field_name) for field_name, _ in self._fields_
        }


class PacketCarTelemetryData(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("m_header", PacketHeader),
        ("m_carTelemetryData", CarTelemetryData * 22),
        ("m_mfdPanelIndex", ctypes.c_uint8),
        ("m_mfdPanelIndexSecondaryPlayer", ctypes.c_uint8),
        ("m_suggestedGear", ctypes.c_int8),
    ]

    def columns(self):
        header_columns = {
            f"m_header_{field_name}": field_type
            for field_name, field_type in PacketHeader().columns().items()
        }
        car_telemetry_data_columns = {
            f"m_carTelemetryData_{field_name}": field_type
            for field_name, field_type in CarTelemetryData().columns().items()
        }

        return {
            **header_columns,
            **car_telemetry_data_columns,
            "m_mfdPanelIndex": ctypes.c_uint8,
            "m_mfdPanelIndexSecondaryPlayer": ctypes.c_uint8,
            "m_suggestedGear": ctypes.c_int8,
        }

    def row(self, car_index):
        header_row = {
            f"m_header_{field_name}": value
            for field_name, value in self.m_header.row().items()
        }
        car_telemetry_data_row = {
            f"m_carTelemetryData_{field_name}": value
            for field_name, value in self.m_carTelemetryData[car_index].row().items()
        }
        return {
            **header_row,
            **car_telemetry_data_row,
            "m_mfdPanelIndex": self.m_mfdPanelIndex,
            "m_mfdPanelIndexSecondaryPlayer": self.m_mfdPanelIndexSecondaryPlayer,
            "m_suggestedGear": self.m_suggestedGear,
        }
