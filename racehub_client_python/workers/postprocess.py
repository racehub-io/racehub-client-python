import pandas as pd
import os
import json
import pyarrow.parquet as pq

from racehub_client_python.workers.websockets import send_message
from racehub_client_python.workers.parsers.writers.motec import write_motec


def format_iracing(df):
    time_parameter = "session_time_elapsed"
    df["timestamp_ms"] = df[time_parameter] * 1e3

    laptime_parameter = "lap_time"
    df["laptime_ms"] = df[laptime_parameter] * 1e3

    return df


def format_f12023(df):
    time_parameter = "m_header_m_sessionTime"
    df["timestamp_ms"] = df[time_parameter] * 1e3

    laptime_parameter = "m_lapData_m_currentLapTimeInMS"
    df["laptime_ms"] = df[laptime_parameter]

    df = df.rename(columns=lambda x: x.replace("m_carDamageData", "CarDam"))
    df = df.rename(columns=lambda x: x.replace("m_carSetupData", "CarSet"))
    df = df.rename(columns=lambda x: x.replace("m_carStatusData", "CarSta"))
    df = df.rename(columns=lambda x: x.replace("m_carTelemetryData", "CarTel"))
    df = df.rename(columns=lambda x: x.replace("m_lapData", "LapD"))
    df = df.rename(columns=lambda x: x.replace("m_lobbyPlayers", "LobPla"))
    df = df.rename(columns=lambda x: x.replace("m_carMotionData", "CarMot"))
    df = df.rename(columns=lambda x: x.replace("m_participantsData", "ParD"))
    df = df.rename(columns=lambda x: x.replace("m_marshalZones", "MarZon"))
    df = df.rename(columns=lambda x: x.replace("m_weatherForecastSample", "WeaFS"))
    df = df.rename(columns=lambda x: x.replace("m_lapHistoryData", "LapHis"))
    df = df.rename(columns=lambda x: x.replace("m_tyreStintsHistoryData", "TyreStn"))
    df = df.rename(columns=lambda x: x.replace("m_tyreSetData", "TyreSet"))
    df = df.rename(columns=lambda x: x.replace("m_classificationData", "ClaD"))

    df = df.rename(columns=lambda x: x.replace("_m_", "_"))

    return df


def format_f12024(df):
    time_parameter = "m_header_m_sessionTime"
    df["timestamp_ms"] = df[time_parameter] * 1e3

    laptime_parameter = "m_lapData_m_currentLapTimeInMS"
    df["laptime_ms"] = df[laptime_parameter]

    df = df.rename(columns=lambda x: x.replace("m_carDamageData", "CarDam"))
    df = df.rename(columns=lambda x: x.replace("m_carSetupData", "CarSet"))
    df = df.rename(columns=lambda x: x.replace("m_carStatusData", "CarSta"))
    df = df.rename(columns=lambda x: x.replace("m_carTelemetryData", "CarTel"))
    df = df.rename(columns=lambda x: x.replace("m_lapData", "LapD"))
    df = df.rename(columns=lambda x: x.replace("m_lobbyPlayers", "LobPla"))
    df = df.rename(columns=lambda x: x.replace("m_carMotionData", "CarMot"))
    df = df.rename(columns=lambda x: x.replace("m_participantsData", "ParD"))
    df = df.rename(columns=lambda x: x.replace("m_marshalZones", "MarZon"))
    df = df.rename(columns=lambda x: x.replace("m_weatherForecastSample", "WeaFS"))
    df = df.rename(columns=lambda x: x.replace("m_lapHistoryData", "LapHis"))
    df = df.rename(columns=lambda x: x.replace("m_tyreStintsHistoryData", "TyreStn"))
    df = df.rename(columns=lambda x: x.replace("m_tyreSetData", "TyreSet"))
    df = df.rename(columns=lambda x: x.replace("m_classificationData", "ClaD"))

    df = df.rename(columns=lambda x: x.replace("_m_", "_"))

    return df


FORMATTERS = {
    2: format_f12023,
    3: format_f12024,
    4: format_iracing,
}


def post_process(archive_path):
    next_progress_threshold = 0

    # iterate through each folder in the archive path
    car_idxs = [
        folder
        for folder in os.listdir(archive_path)
        if os.path.isdir(os.path.join(archive_path, folder))
    ]
    for n_caridx, car_idx in enumerate(car_idxs):
        # check the folder is a directory
        if not os.path.isdir(os.path.join(archive_path, car_idx)):
            continue

        parquet_directory = os.path.join(archive_path, car_idx)

        parquet_paths = [
            os.path.join(parquet_directory, filename)
            for filename in os.listdir(parquet_directory)
            if filename.endswith(".pq")
        ]

        df = pd.concat(
            pd.read_parquet(path, engine="pyarrow") for path in parquet_paths
        )

        df = df.dropna(axis=0, how="all")

        df = df.reset_index(drop=True)

        schema = pq.read_schema(parquet_paths[0])

        metadata = json.loads(schema.metadata[b"racehub"])

        formatter = FORMATTERS.get(metadata["recorder_type"], None)

        if formatter:
            df = formatter(df)
        else:
            send_message(
                "WORKER_RESPONSE_POST_PROCESSOR_ERROR",
                {
                    "archive_path": archive_path,
                    "error": "formatter not found",
                },
            )
            return

        # use metadata["player_name"] if it's not empty otherwise use metadata["driver_name"]
        driver_name = metadata.get("player_name", "")

        if not driver_name or driver_name == "Player":
            driver_name = metadata.get("driver_name", "Unknown")

        metadata["driver_name"] = driver_name

        # make a logical filename for the motec file
        motec_filename = (
            f"Car{car_idx}_"
            f"{driver_name}_"
            f"{metadata.get('driver_nationality', '')}_"
            f"{metadata.get('driver_number', '')}_"
            f"{metadata.get('team_name', '')}_"
            f"{metadata.get('track_name', '')}_"
            f"{metadata.get('event_name', '')}_"
            f"{metadata.get('session_name', '')}.ld"
        )

        motec_filepath = os.path.join(archive_path, motec_filename)

        write_motec(motec_filepath, df, metadata)

        file_progress = ((n_caridx + 1) / len(car_idxs)) * 100

        if file_progress >= next_progress_threshold:
            send_message(
                "WORKER_RESPONSE_POST_PROCESSOR_STATUS",
                {
                    "archive_path": archive_path,
                    "progress": file_progress,
                    "trackName": metadata.get("track_name", ""),
                    "sessionType": metadata.get("session_name", ""),
                },
            )
            next_progress_threshold += 1


def post_process_file(config):
    archive_path = config.get("archive_path")

    send_message(
        "WORKER_RESPONSE_POST_PROCESSOR_STARTED",
        {
            "archive_path": archive_path,
        },
    )

    post_process(archive_path)

    send_message(
        "WORKER_RESPONSE_POST_PROCESSOR_FINISHED",
        {
            "archive_path": archive_path,
        },
    )

