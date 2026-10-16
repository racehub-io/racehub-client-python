import os
import json

from racehub_client_python.constants import DEFAULT_MAPPINGS

racehub_directory = os.path.join(os.path.expanduser("~"), "Documents", "RaceHub")

default_config = {
    "recordings_dir": os.path.join(racehub_directory, "Recordings"),
    "mappings_path": os.path.join(racehub_directory, "mappings.json"),
    "details_path": os.path.join(racehub_directory, "details.json"),
}

# check for existance of config.json
config_filepath = os.path.join(racehub_directory, "config.json")

if not os.path.exists(config_filepath):
    # if not found, create it with default values
    config = default_config

    # create directory if it doesn't exist
    os.makedirs(os.path.dirname(config_filepath), exist_ok=True)

    # save config
    with open(config_filepath, "w") as f:
        json.dump(config, f, indent=4)

else:
    # if found, load it
    with open(config_filepath, "r") as f:
        config = json.load(f)

    # if found, check for missing values and add them
    for key in default_config:
        if key not in config:
            config[key] = default_config[key]

    # save config
    with open(config_filepath, "w") as f:
        json.dump(config, f, indent=4)

# if recordings_dir doesn't exist, create it
os.makedirs(config["recordings_dir"], exist_ok=True)

# if mappings_path doesn't exist, create it
os.makedirs(os.path.dirname(config["mappings_path"]), exist_ok=True)


# if mappings_path doesnt exist create an empty json
if not os.path.exists(config["mappings_path"]):
    with open(config["mappings_path"], "w") as f:
        json.dump(DEFAULT_MAPPINGS, f, indent=4)

# if details_path doesnt exist create an empty json
if not os.path.exists(config["details_path"]):
    with open(config["details_path"], "w") as f:
        json.dump({}, f, indent=4)
