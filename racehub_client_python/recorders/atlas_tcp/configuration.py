import os
import json
from pathlib import Path
from typing import Optional, List, Dict
import logging
import sys

from racehub_client_python.recorders.atlas_tcp.data_types import (
    DataSource,
    ByteOrderType,
    packet_field_type_to_data_type,
    data_type_min_value,
    data_type_max_value,
    default_data_type_format,
    get_packet_field_size,
)

from racehub_client_python.recorders.atlas_tcp.structures import (
    Group,
    RationalConversion,
    SessionConfiguration,
    Configuration,
    Signal,
    Parameter,
    Range,
)

logger = logging.getLogger(__name__)


def build_parameters(
    conversion_name: str,
    packet_parameters: List[dict],
    default_application_group: str,
    frequency_in_hz: float,
):

    groups: Dict[str, Group] = {}
    parameter_target_offset = 0

    for param in packet_parameters:
        # Determine dataType for config
        data_type = packet_field_type_to_data_type(param["packet_field_type"])
        dt_min = param.get("min_value", data_type_min_value(data_type))
        dt_max = param.get("max_value", data_type_max_value(data_type))
        param_format = param.get("format", default_data_type_format(data_type))
        # Byte offset
        offset = param.get("target_byte_offset", parameter_target_offset)
        # Update for next
        param_size = get_packet_field_size(param["packet_field_type"])
        parameter_target_offset = offset + param_size

        param["target_byte_offset"] = offset

        # Build signals
        signals = [
            Signal(
                signal_name=param["name"],
                data_type=data_type,
                data_source=DataSource.PERIODIC,
                frequency=frequency_in_hz,
                start_byte=offset
                + ConfigurationFileOperations.PARAMETERS_START_BYTE_OFFSET,
                num_bits=param.get("num_bits", 8 * param_size),
                start_bit=param.get("start_bit", 0),
            )
        ]
        p = Parameter(
            name=param["name"],
            description=param.get("description", param["name"]),
            conversion_name=conversion_name,
            units=param.get("units", ""),
            fmt=param_format,
            byte_order=(
                ByteOrderType.LITTLE_ENDIAN
                if sys.byteorder == "little"
                else ByteOrderType.BIG_ENDIAN
            ),
            physical_range=Range(dt_min, dt_max),
            warning_range=Range(0, 0),
            signals=signals,
        )

        # Build group path
        group_path = []
        app_group = param.get("application_group", default_application_group)
        group_path.append(app_group)
        if param.get("group_path"):
            group_path.extend(param["group_path"])

        grp = get_or_create_group(groups, group_path)
        grp.Parameters[param["name"]] = p

    return groups, packet_parameters, parameter_target_offset


class ConfigurationFileOperations:
    PARAMETERS_START_BYTE_OFFSET = 8
    ROAMING_CONFIG_PATH = os.path.join(
        os.getenv("APPDATA") or "",
        r"McLaren Applied Technologies\ATLAS 10\Configuration\roaming.user.config",
    )

    @staticmethod
    def get_configuration_file_folder_path() -> str:
        fallback = os.path.join(str(Path.home()), "ConfigurationFiles")
        os.makedirs(fallback, exist_ok=True)

        # first check if the folder is defined in the roaming.user.config
        if ConfigurationFileOperations.ROAMING_CONFIG_PATH and os.path.exists(
            ConfigurationFileOperations.ROAMING_CONFIG_PATH
        ):
            with open(ConfigurationFileOperations.ROAMING_CONFIG_PATH, "r") as f:
                xml_content = f.read()

            import xml.etree.ElementTree as ET

            root = ET.fromstring(xml_content)
            for setting in root.findall(".//setting"):
                if setting.attrib["name"] == "Folders":
                    value = setting.attrib["value"]
                    if value:
                        logger.info(f"Using configuration folder: {value}")
                        return value
                    else:
                        logger.warning(
                            "Folders setting is empty in roaming.user.config."
                        )

        # next check if the folder the config file should have been in exists if so use it
        roaming_config_folder = os.path.dirname(
            ConfigurationFileOperations.ROAMING_CONFIG_PATH
        )
        if os.path.exists(roaming_config_folder):
            logger.info(f"Using configuration folder: {roaming_config_folder}")
            return roaming_config_folder

        # otherwise use the fallback
        logger.warning(
            "Folders setting is not found in roaming.user.config. "
            "Using a local fallback folder named 'ConfigurationFiles' in the user home."
        )
        return fallback

    @staticmethod
    def save_configuration(
        session_configuration: SessionConfiguration,
        config_folder: str,
        configuration_identifier_ref: str,
    ) -> Optional[str]:
        config_dict = {
            "Configuration": session_configuration.Configuration,
            "ATLASParameters": {},
            "Conversions": {},
        }
        # ATLASParameters
        for app_group, group_obj in session_configuration.ATLASParameters.items():
            config_dict["ATLASParameters"][app_group] = (
                ConfigurationFileOperations.group_to_dict(group_obj)
            )
        # Conversions
        for name, conv_obj in session_configuration.Conversions.items():
            if isinstance(conv_obj, RationalConversion):
                cdict = {
                    "Name": conv_obj.Name,
                    "Type": conv_obj.Type,
                    "Coefficients": conv_obj.Coefficients,
                }
                config_dict["Conversions"][name] = cdict
            else:
                config_dict["Conversions"][name] = conv_obj  # fallback

        # If no identifier, create an MD5
        if not session_configuration.Configuration["Identifier"]:
            import hashlib

            text_bytes = json.dumps(config_dict, indent=2).encode("utf-16")
            md5_hash = hashlib.md5(text_bytes).hexdigest().upper()
            session_configuration.Configuration["Identifier"] = md5_hash
            config_dict["Configuration"]["Identifier"] = md5_hash
            configuration_identifier_ref = md5_hash

        if config_folder:
            file_name = f"{session_configuration.Configuration['Identifier']}.json"
            full_path = os.path.join(config_folder, file_name)
            logger.info(f"Saving configuration to {full_path}")
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    json.dump(config_dict, f, indent=2)
                return full_path
            except Exception as e:
                logger.error(f"Error writing TCP recorder configuration file: {e}")
                return None
        return None

    @staticmethod
    def group_to_dict(group_obj: Group) -> dict:
        result = {"Parameters": {}, "SubGroups": {}}
        for pname, param_obj in group_obj.Parameters.items():
            param_dict = {
                "Name": param_obj.Name,
                "Description": param_obj.Description,
                "Conversion": param_obj.ConversionName,
                "Units": param_obj.Units,
                "Format": param_obj.Format,
                "ByteOrder": param_obj.ByteOrder,
                "PhysicalRange": param_obj.PhysicalRange,
                "WarningRange": param_obj.WarningRange,
                "Signals": [],
            }
            # signals
            if param_obj.Signals:
                s_list = []
                for s in param_obj.Signals:
                    s_list.append(
                        {
                            "SignalName": s.SignalName,
                            "DataType": s.DataType,
                            "DataSource": s.DataSource,
                            "Frequency": s.Frequency,
                            "StartByte": s.StartByte,
                            "NumBits": s.NumBits,
                            "StartBit": s.StartBit,
                        }
                    )
                param_dict["Signals"] = s_list
            result["Parameters"][pname] = param_dict

        for sname, sgroup in group_obj.SubGroups.items():
            result["SubGroups"][sname] = ConfigurationFileOperations.group_to_dict(
                sgroup
            )
        return result


def generate_configuration(
    configuration_identifier_ref: str,
    configuration_version: int,
    conversion_name: str,
    groups: Dict[str, Group],
) -> int:
    conversion_name = "Simple1to1"
    conversion = RationalConversion.create_simple_1_to_1(conversion_name)

    session_configuration = SessionConfiguration(
        Configuration(configuration_identifier_ref, str(configuration_version)),
        groups,
        {conversion_name: conversion},
    )
    config_folder = ConfigurationFileOperations.get_configuration_file_folder_path()
    print(f"Config folder: {config_folder}")
    saved_path = ConfigurationFileOperations.save_configuration(
        session_configuration, config_folder, configuration_identifier_ref
    )
    if not saved_path:
        logger.error("Writing configuration file failed!")
        return False
    return True


def get_or_create_group(groups_dict: Dict[str, Group], group_path: List[str]) -> Group:
    current_groups = groups_dict
    group_obj = None
    for gname in group_path:
        if gname not in current_groups:
            new_group = Group()
            current_groups[gname] = new_group
            group_obj = new_group
        else:
            group_obj = current_groups[gname]
        current_groups = group_obj.SubGroups
    if not group_obj:
        group_obj = Group()
    return group_obj
