import os
import numpy as np
import tensorflow as tf

from .preprocessing import (
    resample_model_to_daily, align_dense, align_sparse,
    standardize, build_sequences, train_val_split,
)
from .lstm_model import (
    build_forecast_lstm, train_forecast_lstm, estimate_process_noise,
)
from .enkf import compute_obs_error, run_enkf
from .openloop import run_openloop
from .postprocessing import (
    inverse_transform, compute_ci_bounds, compute_ci_integral, export_results,
)
from .visualization import plot_comparison, plot_ci_area, plot_model_vs_observed


def run_single_reanalysis(model_df, obs_df, variable, station_name,
                          output_dir, hyperparams, seed=42,
                          stop_event=None):
    """Run the full LSTM + EnKF reanalysis for one station-variable pair.

    Parameters
    ----------
    model_df : pd.DataFrame
        Raw model data with DatetimeIndex and 'value' column (sub-daily).
    obs_df : pd.DataFrame
        Observation data with DatetimeIndex and 'value' column.
        May be sparse (with gaps) for TN/TP.
    variable : str
        'discharge', 'TN', or 'TP'.
    station_name : str
    output_dir : str
    hyperparams : dict
    seed : int
    stop_event : threading.Event or None
        If set, the pipeline raises InterruptedError at the next checkpoint.

    Returns
    -------
    dict with summary metrics.
    """
    def _check_stop():
        if stop_event is not None and stop_event.is_set():
            raise InterruptedError("Pipeline cancelled by user")

    np.random.seed(seed)
    tf.random.set_seed(seed)

    lookback = hyperparams["lookback"]
    n_ensemble = hyperparams["n_ensemble"]
    obs_err_factor = hyperparams["obs_error_factor"]

    print(f"\n{'='*70}")
    print(f"  Reanalysis: {station_name} — {variable}")
    print(f"{'='*70}")

    # --- Step 1: Resample model to daily ---
    mdl_daily = resample_model_to_daily(model_df)
    print(f"  Model: {len(mdl_daily)} daily rows "
          f"({mdl_daily.index[0].date()} → {mdl_daily.index[-1].date()})")
    _check_stop()

    # --- Step 2: Determine if sparse or dense observations ---
    obs_count = len(obs_df.dropna(subset=["value"]))
    model_days = len(mdl_daily)

    # Sparse if obs cover less than 50% of model days
    is_sparse = obs_count < model_days * 0.5
    print(f"  Observations: {obs_count} records ({'sparse' if is_sparse else 'dense'})")

    if is_sparse:
        mdl_aligned, obs_aligned, overlap = align_sparse(mdl_daily, obs_df)
        print(f"  Overlap: {overlap} observation days within model period")
    else:
        mdl_aligned, obs_aligned = align_dense(mdl_daily, obs_df)
        overlap = len(obs_aligned)
        print(f"  Overlap: {overlap} common days")

    T = len(mdl_aligned)
    time_idx = mdl_aligned.index
    print(f"  Time series length: {T} days")
    _check_stop()

    # --- Step 3: Standardize ---
    obs_vals = obs_aligned["value"].values
    mdl_vals = mdl_aligned["value"].values

    # For sparse: fit scaler on non-NaN obs values only
    if is_sparse:
        valid_obs = obs_vals[~np.isnan(obs_vals)]
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        scaler.fit(valid_obs.reshape(-1, 1))
        obs_std = np.full((T, 1), np.nan)
        obs_std[~np.isnan(obs_vals), 0] = scaler.transform(
            obs_vals[~np.isnan(obs_vals)].reshape(-1, 1)
        ).flatten()
        mdl_std = scaler.transform(mdl_vals.reshape(-1, 1))
    else:
        obs_std, mdl_std, scaler = standardize(obs_vals, mdl_vals)
    _check_stop()

    # --- Step 4: Build sequences & train LSTM ---
    X_all, y_all = build_sequences(mdl_std, lookback)
    X_train, X_val, y_train, y_val = train_val_split(
        X_all, y_all, hyperparams["train_fraction"]
    )
    print(f"  Sequences: {X_all.shape[0]} total, {X_train.shape[0]} train, {X_val.shape[0]} val")

    lstm = build_forecast_lstm(
        lookback=lookback,
        lstm_units=hyperparams["lstm_units"],
        dense_units=hyperparams["dense_units"],
        lr=hyperparams["learning_rate"],
    )
    history = train_forecast_lstm(
        lstm, X_train, y_train, X_val, y_val,
        epochs=hyperparams["epochs"],
        batch_size=hyperparams["batch_size"],
        patience=hyperparams["patience"],
        verbose=0,
    )
    best_val = min(history.history["val_loss"])
    stopped_epoch = len(history.history["loss"])
    print(f"  LSTM trained — stopped at epoch {stopped_epoch}, best val_loss={best_val:.6f}")
    _check_stop()

    # --- Step 5: Estimate Q and R ---
    Q = estimate_process_noise(lstm, X_train, y_train)
    R = compute_obs_error(obs_std, factor=obs_err_factor)
    print(f"  Q = {Q:.6f} (std={np.sqrt(Q):.4f}), R = {R:.6f} (std={np.sqrt(R):.4f})")
    _check_stop()

    # --- Step 6: Run EnKF ---
    print(f"  Running EnKF — {n_ensemble} members × {T} steps...")
    ens_analysis, ens_forecast = run_enkf(
        lstm, obs_std, mdl_std, Q, R, lookback,
        n_ensemble=n_ensemble, seed=seed,
    )
    print(f"  EnKF complete.")
    _check_stop()

    # --- Step 7: Open-loop baseline ---
    print(f"  Running open-loop baseline...")
    openloop_std = run_openloop(lstm, mdl_std, Q, lookback, seed=seed)
    print(f"  Open-loop complete.")
    _check_stop()

    # --- Step 8: Inverse transform to physical units ---
    rean_mean_std = ens_analysis.mean(axis=1)
    rean_mean_phys = inverse_transform(rean_mean_std, scaler)
    openloop_phys = inverse_transform(openloop_std, scaler)

    # Obs in physical units (preserve NaN for sparse)
    if is_sparse:
        obs_phys = obs_vals.copy()  # already in physical units
    else:
        obs_phys = inverse_transform(obs_std[:, 0], scaler)

    # Model in physical units
    mdl_phys = mdl_vals.copy()

    # Full ensemble -> physical units
    ens_phys = np.zeros_like(ens_analysis)
    for m in range(n_ensemble):
        ens_phys[:, m] = inverse_transform(ens_analysis[:, m], scaler)
    _check_stop()

    # --- Step 9: CI computation ---
    ci_lower, ci_upper = compute_ci_bounds(ens_phys)
    ci_stats = compute_ci_integral(ci_lower, ci_upper)
    print(f"  95% CI integral: {ci_stats['integral']:,.2f}, "
          f"mean width: {ci_stats['mean_width']:.4f}")
    _check_stop()

    # --- Step 10: Export CSVs ---
    os.makedirs(output_dir, exist_ok=True)
    export_results(
        time_idx, obs_phys, openloop_phys, rean_mean_phys,
        ens_phys, output_dir, variable, n_ensemble,
    )
    _check_stop()

    # --- Step 11: Plots ---
    plot_comparison(
        time_idx, obs_phys, openloop_phys, rean_mean_phys,
        variable, station_name, output_dir,
    )
    plot_ci_area(
        time_idx, ci_lower, ci_upper, rean_mean_phys,
        ci_stats["integral"], variable, station_name, output_dir,
    )
    plot_model_vs_observed(
        time_idx, mdl_phys, obs_phys,
        variable, station_name, output_dir,
    )
    _check_stop()

    return {
        "station": station_name,
        "variable": variable,
        "T": T,
        "obs_count": overlap,
        "is_sparse": is_sparse,
        "Q": Q,
        "R": R,
        "best_val_loss": best_val,
        "stopped_epoch": stopped_epoch,
        "ci_integral": ci_stats["integral"],
        "ci_mean_width": ci_stats["mean_width"],
        "ci_max_width": ci_stats["max_width"],
    }
