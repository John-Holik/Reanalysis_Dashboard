"""
pipeline_bridge.py
------------------
Import shim and DataFrame construction helpers for the Streamlit web app.

Inserts Sprint_2/Reanalysis_Pipeline/ into sys.path so that the existing
src/ package can be imported unchanged. Also sets the matplotlib backend
to Agg before any other import to prevent display errors on Windows.
"""

import sys
import io
import matplotlib
matplotlib.use("Agg")  # Must be before any other matplotlib import

import pandas as pd
from pathlib import Path

# ---- Import path setup -----------------------------------------------
# Resolve Sprint_2/Reanalysis_Pipeline/ relative to this file so that
# `from src.pipeline import run_single_reanalysis` works regardless of
# the working directory Streamlit is launched from.
_PIPELINE_ROOT = Path(__file__).parent.parent / "Sprint_2" / "Reanalysis_Pipeline"
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from src.pipeline import run_single_reanalysis  # noqa: E402


# ---- Helper: peek at column names ------------------------------------

def get_csv_columns(uploaded_file) -> list:
    """Return column names from an uploaded CSV without consuming the buffer."""
    buf = io.BytesIO(uploaded_file.read())
    cols = pd.read_csv(buf, nrows=0, encoding="utf-8-sig").columns.tolist()
    uploaded_file.seek(0)
    return cols


def get_csv_unique_values(uploaded_file, column: str) -> list:
    """Return sorted unique values in a column for dropdown population."""
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, usecols=[column], encoding="utf-8-sig")
    uploaded_file.seek(0)
    return sorted(df[column].dropna().astype(str).str.strip().unique().tolist())


def get_csv_numeric_columns(uploaded_file) -> list:
    """Return column names that contain numeric (int/float) data.

    Parameters
    ----------
    uploaded_file : UploadedFile
        Streamlit uploaded file object.

    Returns
    -------
    list of str
        Column names whose dtype is numeric. If no numeric columns are
        found, returns all column names as a fallback.
    """
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, nrows=100, encoding="utf-8-sig")
    uploaded_file.seek(0)
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return numeric if numeric else df.columns.tolist()


def get_csv_preview(uploaded_file, nrows: int = 5) -> pd.DataFrame:
    """Return first nrows of an uploaded CSV as a DataFrame for display.

    Parameters
    ----------
    uploaded_file : UploadedFile
        Streamlit uploaded file object.
    nrows : int
        Number of rows to return. Default 5 per UI-SPEC D-06.

    Returns
    -------
    pd.DataFrame
        First nrows of the CSV, all columns, original dtypes.
    """
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, nrows=nrows, encoding="utf-8-sig")
    uploaded_file.seek(0)
    return df


# ---- DataFrame constructors ------------------------------------------

def build_model_df(uploaded_file) -> dict:
    """
    Parse the model CSV (columns: SimDate, Flow, TN, TP) and return a dict
    mapping variable name to a DataFrame with DatetimeIndex and 'value' column.

    Returns
    -------
    dict with keys 'discharge', 'TN', 'TP'
    """
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, encoding="utf-8-sig")
    df["time"] = pd.to_datetime(df["SimDate"], format="mixed", dayfirst=False)
    df = df.set_index("time").sort_index()

    col_map = {"discharge": "Flow", "TN": "TN", "TP": "TP"}
    result = {}
    for variable, col in col_map.items():
        result[variable] = df[[col]].rename(columns={col: "value"})
    return result


def build_obs_df_dedicated(uploaded_file, date_col: str, value_col: str,
                            convert_factor: float = 1.0) -> pd.DataFrame:
    """
    Parse a dedicated single-variable observation CSV (one date + one value column).

    Returns
    -------
    pd.DataFrame with DatetimeIndex and 'value' column in converted units.
    """
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, encoding="utf-8-sig")
    df["time"] = pd.to_datetime(df[date_col], format="mixed", dayfirst=False)
    df = df[["time", value_col]].rename(columns={value_col: "value"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce") * convert_factor
    df = df.set_index("time").sort_index().dropna(subset=["value"])
    return df


def build_obs_df_multi_station(uploaded_file, date_col: str, value_col: str,
                                station_col: str, station_filter: str,
                                param_col: str, param_filter: str,
                                convert_factor: float = 1.0) -> pd.DataFrame:
    """
    Parse a multi-station water quality CSV (e.g., HU8 TN/TP files).
    Filters by station and parameter, aggregates duplicates to daily mean.

    Uses utf-8-sig encoding to handle BOM present in HU8 observation files.

    Returns
    -------
    pd.DataFrame with DatetimeIndex and 'value' column in converted units.
    """
    buf = io.BytesIO(uploaded_file.read())
    df = pd.read_csv(buf, encoding="utf-8-sig")

    mask = (
        df[station_col].astype(str).str.strip() == str(station_filter).strip()
    ) & (
        df[param_col].astype(str).str.strip() == str(param_filter).strip()
    )
    subset = df[mask].copy()

    subset["time"] = pd.to_datetime(subset[date_col], format="mixed", dayfirst=False)
    subset["value"] = pd.to_numeric(subset[value_col], errors="coerce") * convert_factor
    subset = subset.dropna(subset=["value"])
    subset = subset.set_index("time")[["value"]].sort_index()
    daily = subset.resample("D").mean().dropna()
    return daily
