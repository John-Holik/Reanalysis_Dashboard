import numpy as np
import tensorflow as tf

from ..lstm_model import build_forecast_lstm, train_forecast_lstm


class LSTMForecastModel:
    """Keras LSTM wrapped in the ForecastModel interface.

    Owns the tf.function compilation and tf.Variable pre-allocation
    so that enkf.py and openloop.py have zero TensorFlow imports.
    """

    def __init__(self, lookback: int, lstm_units: int = 64,
                 dense_units: int = 64, lr: float = 1e-3):
        self._model = build_forecast_lstm(
            lookback, lstm_units=lstm_units, dense_units=dense_units, lr=lr
        )
        self._fast_predict = None
        self._batch_tf = None

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """Train the LSTM and compile the tf.function for fast inference.

        Returns
        -------
        tf.keras.callbacks.History
        """
        history = train_forecast_lstm(
            self._model, X_train, y_train, X_val, y_val, **kwargs
        )

        # Build fast-predict wrapper once, after training
        keras_model = self._model

        @tf.function(reduce_retracing=True)
        def _fp(x):
            return keras_model(x, training=False)

        self._fast_predict = _fp

        # Pre-allocate persistent tensor sized for the filter batch
        n_ensemble = X_train.shape[0]  # over-estimated; resized on first call
        lookback = X_train.shape[1]
        n_state = X_train.shape[2]
        self._batch_tf = tf.Variable(
            tf.zeros((n_ensemble, lookback, n_state), dtype=tf.float32)
        )

        # Warm up — forces trace before the tight filter loop
        dummy = X_train[:1].astype(np.float32)
        if self._batch_tf.shape[0] != 1:
            warm_tf = tf.Variable(tf.zeros((1, lookback, n_state), dtype=tf.float32))
            warm_tf.assign(dummy)
            _ = self._fast_predict(warm_tf)
        else:
            self._batch_tf.assign(dummy)
            _ = self._fast_predict(self._batch_tf)

        return history

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Predict for n_ensemble members in one batched call.

        Parameters
        ----------
        X : np.ndarray, shape (n_ensemble, lookback, 1)

        Returns
        -------
        np.ndarray, shape (n_ensemble, 1)
        """
        n = X.shape[0]
        if self._batch_tf.shape[0] != n:
            self._batch_tf = tf.Variable(
                tf.zeros(X.shape, dtype=tf.float32)
            )
        self._batch_tf.assign(X.astype(np.float32))
        return self._fast_predict(self._batch_tf).numpy()

    def predict_sequences(self, X: np.ndarray) -> np.ndarray:
        """Predict over the full training set for Q estimation.

        Parameters
        ----------
        X : np.ndarray, shape (N, lookback, 1)

        Returns
        -------
        np.ndarray, shape (N, 1)
        """
        return self._model.predict(X, verbose=0)
