import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def resample_model_to_daily(model_df):
    """Resample sub-daily model data to daily means.

    Parameters
    ----------
    model_df : pd.DataFrame
        Model data with DatetimeIndex and 'value' column (sub-daily).

    Returns
    -------
    pd.DataFrame with daily DatetimeIndex and 'value' column.
    """
    daily = model_df.resample("D").mean().dropna()
    return daily


def align_dense(model_daily, obs_df):
    """Align model and observation data via inner-join on dates.

    For dense observations (e.g. daily discharge).

    Returns
    -------
    (model_aligned, obs_aligned) : tuple of pd.DataFrame
    """
    common = model_daily.index.intersection(obs_df.index)
    return model_daily.loc[common].copy(), obs_df.loc[common].copy()


def align_sparse(model_daily, obs_df):
    """Align model and sparse observations for intermittent EnKF.

    Creates a full daily series from the model period. Observation values
    are placed on matching dates; all other dates are NaN.

    Returns
    -------
    (model_aligned, obs_full) : tuple of pd.DataFrame
        obs_full has NaN on days without observations.
    overlap_count : int
        Number of days with actual observations.
    """
    # Restrict to dates where model exists
    obs_in_range = obs_df[obs_df.index.isin(model_daily.index)]

    # Create full daily obs series with NaN fill
    obs_full = pd.DataFrame(index=model_daily.index, columns=["value"], dtype=float)
    obs_full.loc[obs_in_range.index, "value"] = obs_in_range["value"].values

    overlap_count = obs_full["value"].notna().sum()
    return model_daily.copy(), obs_full, int(overlap_count)


def standardize(obs_values, mdl_values):
    """Fit StandardScaler on observations, transform both arrays.

    Parameters
    ----------
    obs_values : np.ndarray, shape (N,) or (N, 1)
    mdl_values : np.ndarray, shape (N,) or (N, 1)

    Returns
    -------
    obs_std : np.ndarray, shape (N, 1)
    mdl_std : np.ndarray, shape (N, 1)
    scaler : StandardScaler (fitted)
    """
    obs_2d = obs_values.reshape(-1, 1) if obs_values.ndim == 1 else obs_values
    mdl_2d = mdl_values.reshape(-1, 1) if mdl_values.ndim == 1 else mdl_values

    scaler = StandardScaler()
    obs_std = scaler.fit_transform(obs_2d)
    mdl_std = scaler.transform(mdl_2d)
    return obs_std, mdl_std, scaler


def build_sequences(data, lookback):
    """Create sliding-window (X, y) pairs for LSTM training.

    Parameters
    ----------
    data : np.ndarray, shape (T, 1)
    lookback : int

    Returns
    -------
    X : np.ndarray, shape (T - lookback, lookback, 1)
    y : np.ndarray, shape (T - lookback, 1)
    """
    X, y = [], []
    for i in range(len(data) - lookback):
        X.append(data[i : i + lookback])
        y.append(data[i + lookback])
    return np.array(X), np.array(y)


def train_val_split(X, y, train_fraction=0.8):
    """Temporal train/val split (no shuffling).

    Returns
    -------
    X_train, X_val, y_train, y_val
    """
    split = int(len(X) * train_fraction)
    return X[:split], X[split:], y[:split], y[split:]
