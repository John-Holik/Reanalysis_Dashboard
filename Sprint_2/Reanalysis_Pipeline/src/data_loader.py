import os
import pandas as pd
import numpy as np

# Cache for large observation files so we only read them once
_obs_file_cache = {}


def load_model_data(model_path, variable):
    """Load model CSV and return a single-column DataFrame with DatetimeIndex.

    Parameters
    ----------
    model_path : str
        Path to the model CSV (columns: SimDate, Flow, TN, TP).
    variable : str
        One of 'discharge', 'TN', 'TP'.

    Returns
    -------
    pd.DataFrame with DatetimeIndex and column 'value'.
    """
    col_map = {"discharge": "Flow", "TN": "TN", "TP": "TP"}
    raw_col = col_map[variable]

    df = pd.read_csv(model_path)
    df["time"] = pd.to_datetime(df["SimDate"], format="mixed", dayfirst=False)
    df = df[["time", raw_col]].rename(columns={raw_col: "value"})
    df = df.set_index("time").sort_index()
    return df


def load_obs_dedicated_discharge(obs_dir, obs_cfg):
    """Load a dedicated discharge CSV (e.g. Oserved flow_ARCADIA_FL.csv).

    Returns
    -------
    pd.DataFrame with DatetimeIndex and column 'value' (daily, CMS).
    """
    path = os.path.join(obs_dir, obs_cfg["file"])
    date_col = obs_cfg["date_col"]
    value_col = obs_cfg["value_col"]

    df = pd.read_csv(path, parse_dates=[date_col])
    df = df[[date_col, value_col]].rename(columns={date_col: "time", value_col: "value"})
    df = df.set_index("time").sort_index()
    df = df.dropna(subset=["value"])
    return df


def load_obs_multi_station(obs_dir, obs_cfg):
    """Load TN or TP observations from a multi-station HU8 CSV.

    Filters by StationID and Parameter, converts units, aggregates duplicates
    per date to a daily mean.

    Returns
    -------
    pd.DataFrame with DatetimeIndex and column 'value' (in mg/L after conversion).
    """
    path = os.path.join(obs_dir, obs_cfg["file"])

    # Use cache to avoid re-reading large files
    if path not in _obs_file_cache:
        _obs_file_cache[path] = pd.read_csv(path, encoding="utf-8-sig")
    full_df = _obs_file_cache[path]

    station_filter = str(obs_cfg["station_id_filter"]).strip()
    param_filter = obs_cfg["parameter_filter"]
    date_col = obs_cfg["date_col"]
    value_col = obs_cfg["value_col"]
    convert = obs_cfg.get("convert_factor", 1.0)

    # Strip whitespace from StationID for matching
    mask_station = full_df["StationID"].astype(str).str.strip() == station_filter
    mask_param = full_df["Parameter"] == param_filter
    subset = full_df[mask_station & mask_param].copy()

    if subset.empty:
        # Also try matching on Actual_StationID
        if "Actual_StationID" in full_df.columns:
            mask_actual = full_df["Actual_StationID"].astype(str).str.strip() == station_filter
            subset = full_df[mask_actual & mask_param].copy()

    if subset.empty:
        print(f"  WARNING: No observations found for station={station_filter}, param={param_filter}")
        return pd.DataFrame(columns=["value"])

    subset["time"] = pd.to_datetime(subset[date_col], format="mixed", dayfirst=False)
    subset["value"] = pd.to_numeric(subset[value_col], errors="coerce") * convert
    subset = subset.dropna(subset=["value", "time"])

    # Aggregate duplicate dates (multiple depths/replicates) -> daily mean
    subset = subset.set_index("time")[["value"]].sort_index()
    daily = subset.resample("D").mean().dropna()

    return daily


def load_observations(obs_dir, obs_cfg, dirs=None):
    """Dispatch to the correct loader based on observation type.

    Parameters
    ----------
    obs_dir : str
        Default directory containing observation files.
    obs_cfg : dict
        Observation config from pipeline_config.yaml.
    dirs : dict, optional
        Mapping of dir keys (e.g. 'model_data_dir') to resolved paths.
        Used when a specific obs entry overrides the default directory.

    Returns
    -------
    pd.DataFrame with DatetimeIndex and column 'value'.
    """
    if obs_cfg is None:
        return pd.DataFrame(columns=["value"])

    # Allow per-entry directory override via 'dir' key in config
    actual_dir = obs_dir
    if dirs and "dir" in obs_cfg:
        actual_dir = dirs.get(obs_cfg["dir"], obs_dir)

    obs_type = obs_cfg["type"]
    if obs_type == "dedicated_discharge":
        return load_obs_dedicated_discharge(actual_dir, obs_cfg)
    elif obs_type == "multi_station":
        return load_obs_multi_station(actual_dir, obs_cfg)
    else:
        raise ValueError(f"Unknown observation type: {obs_type}")


def check_data_availability(config, config_dir):
    """Scan all station-variable pairs and report observation counts and overlap.

    Returns
    -------
    pd.DataFrame with columns: station_id, station_name, variable, obs_count,
    model_start, model_end, obs_start, obs_end, overlap_days.
    """
    from .config import resolve_path

    model_dir = resolve_path(config_dir, config["paths"]["model_data_dir"])
    obs_dir = resolve_path(config_dir, config["paths"]["observation_data_dir"])
    dirs = {
        "model_data_dir": model_dir,
        "observation_data_dir": obs_dir,
    }

    rows = []
    for st in config["stations"]:
        model_path = os.path.join(model_dir, st["model_file"])

        for variable in ["discharge", "TN", "TP"]:
            obs_cfg = st["observations"].get(variable)

            row = {
                "station_id": st["station_id"],
                "station_name": st["name"],
                "variable": variable,
            }

            if obs_cfg is None:
                row.update({"obs_count": 0, "overlap_days": 0, "status": "NO OBS"})
                rows.append(row)
                continue

            # Load model
            mdl = load_model_data(model_path, variable)
            mdl_daily = mdl.resample("D").mean().dropna()
            row["model_start"] = str(mdl_daily.index.min().date())
            row["model_end"] = str(mdl_daily.index.max().date())

            # Load observations
            obs = load_observations(obs_dir, obs_cfg, dirs=dirs)
            row["obs_count"] = len(obs)

            if len(obs) == 0:
                row.update({"overlap_days": 0, "status": "NO OBS"})
                rows.append(row)
                continue

            row["obs_start"] = str(obs.index.min().date())
            row["obs_end"] = str(obs.index.max().date())

            # Compute overlap
            common = mdl_daily.index.intersection(obs.index)
            row["overlap_days"] = len(common)

            min_days = config["hyperparameters"]["min_overlap_days"]
            if len(common) >= min_days:
                row["status"] = "GO"
            else:
                row["status"] = f"LOW OVERLAP ({len(common)} < {min_days})"

            rows.append(row)

    return pd.DataFrame(rows)
