import pandas as pd
import json
import numpy as np
from racehub_client_python import config
from racehub_client_python.workers.websockets import send_message
from racehub_client_python.workers.parsers.writers.sessiondetails import SessionDetails
from racehub_client_python.workers.parsers.writers.motecwriter import MotecWriter
from racehub_client_python.constants import RECORDER_TYPES_INV


def downcast(df):
    # Select columns to downcast
    float_cols = df.select_dtypes(include=["float"]).columns
    int_cols = df.select_dtypes(include=["int"]).columns

    # Downcast
    df[float_cols] = df[float_cols].apply(pd.to_numeric, downcast="float")
    df[int_cols] = df[int_cols].apply(pd.to_numeric, downcast="integer")

    return df


def write_motec(output_filepath, raw_df, metadata):
    # create a dictionary of parameters defaulted for all columns in raw_df
    parameters = {}

    raw_df = raw_df.select_dtypes(include=["number"])

    for col in raw_df.columns:
        parameter = {
            "identifier": col,
            "name": col,
            "unit": "",
        }
        parameters[col] = parameter

    # Copy original dataframe
    output_df = raw_df.copy()

    # load the mappings
    with open(config["mappings_path"]) as f:
        mappings_config = json.load(f)

    recorder_type_name = RECORDER_TYPES_INV[metadata["recorder_type"]]
    mappings = mappings_config.get(recorder_type_name, [])

    for mapping in mappings:
        # handle exceptions for the mappings
        # first check the mapping["input"] is in the output_df
        # if not, skip the mapping

        if mapping["input"] not in output_df.columns:
            send_message(
                "WORKER_RESPONSE_POST_PROCESSOR_ERROR",
                {
                    "message": "input %s not in output_df" % mapping["input"],
                },
            )
            continue

        # check that the output_df[mapping["input"]] is numeric
        # if not, skip the mapping

        if not pd.api.types.is_numeric_dtype(output_df[mapping["input"]]):
            send_message(
                "WORKER_RESPONSE_POST_PROCESSOR_ERROR",
                {
                    "message": "input %s is not numeric" % mapping["input"],
                },
            )
            continue

        # check that both the scalar and offset are numeric
        # if not, skip the mapping

        if not (
            isinstance(mapping["scalar"], (int, float))
            and isinstance(mapping["offset"], (int, float))
        ):
            send_message(
                "WORKER_RESPONSE_POST_PROCESSOR_ERROR",
                {
                    "message": "scalar or offset is not numeric for %s"
                    % mapping["input"],
                },
            )
            continue

        output_df[mapping["name"]] = (
            output_df[mapping["input"]] * mapping["scalar"] + mapping["offset"]
        )

        parameters[mapping["name"]] = {
            "identifier": mapping["name"],
            "name": mapping["name"],
            "unit": mapping["unit"],
        }

    # convert the timestamp to a datetime and make it the index
    output_df["index"] = pd.to_datetime(output_df["timestamp_ms"] * 1e6, unit="ns")

    output_df = output_df.set_index(["index"], drop=True)

    # create a new index with 25hz
    new_index = pd.date_range(
        start=output_df.index[0],
        end=output_df.index[-1],
        freq="40ms",
    )

    output_df = output_df.groupby(output_df.index).agg("first")

    # reindex output_df
    output_df = output_df.reindex(new_index, method="nearest")

    output_df = output_df.ffill()

    output_df = output_df.fillna(0)

    # downcast the dataframe
    output_df = downcast(output_df)

    cols_to_drop = [
        col
        for col in output_df.columns
        if (
            output_df[col].dtype == np.dtype("int64")
            or output_df[col].dtype == np.dtype("float64")
            or abs(output_df[col].max()) > 2**31
            or abs(output_df[col].min()) > 2**31
        )
    ]

    if cols_to_drop:
        send_message(
            "WORKER_RESPONSE_POST_PROCESSOR_MESSAGE",
            {
                "message": "Dropping columns: %s" % cols_to_drop,
            },
        )

    # find any columns with names that are longer than 32 characters
    cols_abv = [col for col in output_df.columns if len(col) > 32]

    if cols_abv:
        send_message(
            "WORKER_RESPONSE_POST_PROCESSOR_MESSAGE",
            {"message": "Columns with names longer than 32 characters: %s" % cols_abv},
        )

    cols_to_drop.extend(cols_abv)

    if cols_to_drop:
        output_df = output_df.drop(columns=cols_to_drop)

    output_df = output_df.reset_index(drop=True)

    w = MotecWriter(output_filepath)

    # remove session_id from metadata
    metadata.pop("session_id")

    # convert session_date to datetime
    session_timestamp = pd.to_datetime(metadata.get("session_timestamp", 0), unit="s")

    session_details = SessionDetails(
        session_timestamp=session_timestamp,
        series=metadata.get("series", ""),
        event_name=metadata.get("event_name", ""),
        session_name=metadata.get("session_name", ""),
        vehicle_type=metadata.get("vehicle_type", ""),
        vehicle_comment="",
        track_name=metadata.get("track_name", ""),
        track_length=int(metadata.get("track_length", 0)),
        air_temp=metadata.get("air_temp", 0),
        track_temp=metadata.get("track_temp", 0),
        driver_name=metadata.get("driver_name", ""),
        driver_abbreviation=metadata.get("driver_abbreviation", ""),
        driver_number=metadata.get("driver_number", 0),
        driver_nationality=metadata.get("driver_nationality", ""),
        team_name=metadata.get("team_name", ""),
    )

    laps = process_laps(raw_df)

    with open(config["details_path"], "r") as f:
        details_configs = json.load(f)

    ldx_details = []
    for details_config in details_configs:
        col = details_config["input"]
        if col in output_df.columns:
            ldx_details.append(
                {
                    "name": details_config["name"],
                    "value": output_df[col].mode()[0],
                    "type": details_config["type"],
                    "unit": details_config["unit"],
                    "decimals": details_config["decimals"],
                }
            )

    w.write(output_df, parameters, laps, session_details, ldx_details)


def process_laps(df):
    # Initialize lap_change column with False values
    df["lap_change"] = False

    # convert laptime_ms to int
    df["laptime_ms"] = df["laptime_ms"].astype(int)

    # calculate the gradient of the laptime_ms column
    df["laptime_ms_gradient"] = df["laptime_ms"].diff()

    # create a mask for the gradient column where the value is less than 0
    mask = df["laptime_ms_gradient"].abs() > 10000

    # # in each group of consecutive True values, set the first value to True
    df["lap_change"] = mask & ~mask.shift(fill_value=False)

    # also remove True values that are within 1 second of another True value
    df["time_diff"] = df.loc[df["lap_change"], "timestamp_ms"].diff()

    df["lap_change"] = df["lap_change"] & (
        (df["time_diff"] > 1000) | df["time_diff"].isna()
    )
    df.drop(columns=["time_diff"], inplace=True)

    # Compute group labels
    df["group_label"] = df["lap_change"].cumsum()

    # Compute start and end times for each group
    start_times = df.groupby("group_label")["timestamp_ms"].min() / 1e3
    end_times = df.groupby("group_label")["timestamp_ms"].max() / 1e3

    # Create a DataFrame with the computed values
    laps = pd.DataFrame(
        {
            "start_time": start_times.values,
            "end_time": end_times.values,
            "number": np.arange(1, len(start_times) + 1),  # Lap numbers start from 1
        }
    )

    return laps
