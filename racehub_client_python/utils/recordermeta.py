import os
import json

from racehub_client_python import config


def load_recorder_metadata():
    recorder_meta_path = os.path.join(config["recordings_dir"], "recorderMeta.json")

    if os.path.exists(recorder_meta_path):
        with open(recorder_meta_path, "r") as f:
            return json.load(f)

    return {}


def get_recorder_metadata():
    metadata = load_recorder_metadata()

    # iterate through each folder in the recordings directory, if the folder has rhc files in it, then it's an archive
    for root, dirs, files in os.walk(config["recordings_dir"]):
        if any(filename.endswith(".rhc") for filename in files):
            # check if the archive is already in the metadata
            if root in metadata:
                # if it is, then we don't need to do anything
                continue
            metadata[root] = {
                "partitions": {},
                "all_partitions_parsed": False,
                "post_processed": False,
            }

            # add each rhc partition to the metadata
            for filename in files:
                if filename.endswith(".rhc"):
                    # check if the partition is already in the metadata
                    if filename in metadata[root]["partitions"]:
                        # if it is, then we don't need to do anything
                        continue

                    metadata[root]["partitions"][filename] = {
                        "parsed": False,
                    }

                    # TODO: check if there has been a .pq file created for this partition, this needs more logic as the .pqs are made per participant
                    # metadata[root]["partitions"][filepath]["parsed"] = True

                    # if we've just added a new partition, then we need to set the archive to not be fully parsed
                    metadata[root]["all_partitions_parsed"] = False
                    metadata[root]["post_processed"] = False

    return metadata


def save_recorder_metadata(metadata):
    recorder_meta_path = os.path.join(config["recordings_dir"], "recorderMeta.json")

    with open(recorder_meta_path, "w") as f:
        json.dump(metadata, f)
