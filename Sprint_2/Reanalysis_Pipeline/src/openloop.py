import numpy as np


def run_openloop(forecast_model, mdl_std, Q, lookback, n_state=1, seed=42):
    """Generate open-loop baseline: forecast model + process noise, no assimilation.

    Parameters
    ----------
    forecast_model : ForecastModel
        Any model satisfying the ForecastModel protocol (LSTM, XGBoost, etc.).
    mdl_std : np.ndarray, shape (T, 1)
        Standardized model data.
    Q : float
        Process noise variance.
    lookback : int
    n_state : int
    seed : int

    Returns
    -------
    openloop_std : np.ndarray, shape (T,)
    """
    np.random.seed(seed + 1)
    T = len(mdl_std)

    openloop_std = np.zeros(T)
    openloop_std[:lookback] = mdl_std[:lookback, 0]

    history = mdl_std[:lookback].copy().reshape(1, lookback, n_state)

    # Pre-generate all noise
    noise_all = np.random.normal(0, np.sqrt(Q), size=T)

    for t in range(lookback, T):
        pred = forecast_model.predict_batch(history)[0, 0]
        openloop_std[t] = pred + noise_all[t]

        history[0, :-1, 0] = history[0, 1:, 0]
        history[0, -1, 0] = openloop_std[t]

        if (t + 1) % 2000 == 0:
            print(f"  Open-loop t = {t+1:,}/{T:,}")

    return openloop_std
