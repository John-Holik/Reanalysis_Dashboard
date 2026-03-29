import numpy as np
import tensorflow as tf


def run_openloop(lstm_model, mdl_std, Q, lookback, n_state=1, seed=42):
    """Generate open-loop baseline: LSTM + process noise, no assimilation.

    Parameters
    ----------
    lstm_model : trained Keras LSTM model
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

    # Compile a fast prediction function
    @tf.function(reduce_retracing=True)
    def fast_predict(x):
        return lstm_model(x, training=False)

    history = mdl_std[:lookback].copy().reshape(1, lookback, n_state)

    # Pre-allocate persistent tensor
    hist_tf = tf.Variable(tf.zeros((1, lookback, n_state), dtype=tf.float32))

    # Pre-generate all noise
    noise_all = np.random.normal(0, np.sqrt(Q), size=T)

    # Warm up
    hist_tf.assign(history.astype(np.float32))
    _ = fast_predict(hist_tf)

    for t in range(lookback, T):
        hist_tf.assign(history.astype(np.float32))
        pred = fast_predict(hist_tf).numpy()[0, 0]
        openloop_std[t] = pred + noise_all[t]

        history[0, :-1, 0] = history[0, 1:, 0]
        history[0, -1, 0] = openloop_std[t]

        if (t + 1) % 2000 == 0:
            print(f"  Open-loop t = {t+1:,}/{T:,}")

    return openloop_std
