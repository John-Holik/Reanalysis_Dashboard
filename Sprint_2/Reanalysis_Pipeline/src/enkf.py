import numpy as np


def compute_obs_error(obs_std, factor=0.2):
    """Compute observation error variance R.

    R = factor * Var(obs_std), ignoring NaN values.
    """
    valid = obs_std[~np.isnan(obs_std)]
    obs_var = float(np.var(valid, ddof=1))
    return factor * obs_var


def run_enkf(forecast_model, obs_std, mdl_std, Q, R, lookback,
             n_ensemble=50, n_state=1, seed=42):
    """Run Ensemble Kalman Filter with intermittent assimilation.

    Supports sparse observations: analysis step is only performed on
    time steps where obs_std is non-NaN. On other steps, the forecast
    becomes the analysis (no correction).

    Parameters
    ----------
    forecast_model : ForecastModel
        Any model satisfying the ForecastModel protocol (LSTM, XGBoost, etc.).
        Called via forecast_model.predict_batch(X) where X has shape
        (n_ensemble, lookback, n_state).
    obs_std : np.ndarray, shape (T, 1)
        Standardized observations. NaN on days without data.
    mdl_std : np.ndarray, shape (T, 1)
        Standardized model data (used for history initialization).
    Q : float
        Process noise variance.
    R : float
        Observation error variance.
    lookback : int
    n_ensemble : int
    n_state : int
    seed : int

    Returns
    -------
    ens_analysis : np.ndarray, shape (T, n_ensemble)
    ens_forecast : np.ndarray, shape (T, n_ensemble)
    """
    np.random.seed(seed)
    T = len(obs_std)

    ens_forecast = np.zeros((T, n_ensemble))
    ens_analysis = np.zeros((T, n_ensemble))

    # Initialize ensemble from first valid observation + small noise
    first_obs = obs_std[0, 0] if not np.isnan(obs_std[0, 0]) else mdl_std[0, 0]
    ens_analysis[0, :] = first_obs + np.random.normal(0, 0.01, size=n_ensemble)

    # History buffer per member: (M, lookback, n_state)
    histories = np.tile(mdl_std[:lookback].T, (n_ensemble, 1, 1)).transpose(0, 2, 1)
    # shape: (n_ensemble, lookback, n_state)

    # Pre-compute constants
    sqrt_Q = np.sqrt(Q)
    sqrt_R = np.sqrt(R)

    # Pre-generate all random numbers at once (much faster than per-step)
    proc_noise_all = np.random.normal(0, sqrt_Q, size=(T, n_ensemble))
    obs_noise_all = np.random.normal(0, sqrt_R, size=(T, n_ensemble))

    # Flatten obs to 1-D for fast indexing; pre-compute observation mask
    obs_flat = obs_std[:, 0]
    has_obs_mask = ~np.isnan(obs_flat)

    # EnKF loop
    for t in range(lookback, T):
        # -- Forecast step (single batched call) --
        preds = forecast_model.predict_batch(histories)  # (M, 1)

        x_f = preds[:, 0] + proc_noise_all[t]           # (M,)
        ens_forecast[t, :] = x_f

        # -- Analysis step (fully vectorized) --
        if has_obs_mask[t]:
            P_f = np.var(x_f, ddof=1)
            K = P_f / (P_f + R)

            y_pert = obs_flat[t] + obs_noise_all[t]      # (M,)
            ens_analysis[t, :] = x_f + K * (y_pert - x_f)
        else:
            ens_analysis[t, :] = x_f

        # -- Update history buffers (vectorized shift) --
        histories[:, :-1, 0] = histories[:, 1:, 0]
        histories[:, -1, 0] = ens_analysis[t, :]

        if (t + 1) % 2000 == 0:
            status = f"K={K:.4f}" if has_obs_mask[t] else "no obs"
            print(f"  t = {t+1:,}/{T:,}  |  {status}")

    # Fill first LOOKBACK rows
    for t in range(lookback):
        if has_obs_mask[t]:
            ens_analysis[t, :] = obs_flat[t]
        else:
            ens_analysis[t, :] = mdl_std[t, 0]
        ens_forecast[t, :] = mdl_std[t, 0]

    return ens_analysis, ens_forecast
