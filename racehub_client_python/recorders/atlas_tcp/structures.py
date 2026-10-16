from typing import Dict

from racehub_client_python.recorders.atlas_tcp.data_types import ConversionType


class Configuration:
    def __init__(self, identifier: str = "", version: str = ""):
        self.Identifier: str = identifier
        self.Version: str = version


class Range:
    def __init__(self, minimum=0.0, maximum=0.0):
        self.Min = min(minimum, maximum)
        self.Max = max(minimum, maximum)


class Parameter:
    def __init__(
        self,
        name: str,
        description: str,
        conversion_name: str,
        units: str,
        fmt: str,
        byte_order: str,
        physical_range: Range,
        warning_range: Range,
        signals: list,
    ):
        self.Name = name
        self.Description = description
        self.ConversionName = conversion_name
        self.Units = units
        self.Format = fmt
        self.ByteOrder = byte_order
        self.PhysicalRange = {"Min": physical_range.Min, "Max": physical_range.Max}
        self.WarningRange = {"Min": warning_range.Min, "Max": warning_range.Max}
        self.Signals = signals


class Group:
    def __init__(self, sub_groups=None, parameters=None):
        self.SubGroups: Dict[str, "Group"] = sub_groups or {}
        self.Parameters: Dict[str, Parameter] = parameters or {}


class SessionConfiguration:
    def __init__(
        self,
        configuration: Configuration,
        application_groups: Dict[str, Group],
        conversions: Dict[str, dict],
    ):
        self.Configuration = {
            "Identifier": configuration.Identifier,
            "Version": configuration.Version,
        }
        self.ATLASParameters = application_groups
        self.Conversions = conversions


class RationalConversion:
    def __init__(self, name: str):
        self.Name = name
        self.Type = ConversionType.RATIONAL
        self.Coefficients = [0.0, 1.0, 0.0, 0.0, 0.0, 1.0]

    @staticmethod
    def create_simple_1_to_1(name: str):
        return RationalConversion(name)


class Signal:
    def __init__(
        self,
        signal_name: str,
        data_type: str,
        data_source: str,
        frequency: float,
        start_byte: int,
        num_bits: int,
        start_bit: int,
    ):
        self.SignalName = signal_name
        self.DataType = data_type
        self.DataSource = data_source
        self.Frequency = frequency
        self.StartByte = start_byte
        self.NumBits = num_bits
        self.StartBit = start_bit
