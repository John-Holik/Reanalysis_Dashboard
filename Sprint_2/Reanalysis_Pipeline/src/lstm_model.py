import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks


def build_forecast_lstm(lookback, n_state=1, lstm_units=64, dense_units=64, lr=1e-3):
    """Build a regression LSTM for single-variable forecasting.

    Architecture: LSTM(units) -> Dense(dense_units, relu) -> Dense(n_state, linear)
    """
    model = models.Sequential([
        layers.LSTM(lstm_units, input_shape=(lookback, n_state)),
        layers.Dense(dense_units, activation="relu"),
        layers.Dense(n_state, activation="linear"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss="mse",
    )
    return model


def train_forecast_lstm(model, X_train, y_train, X_val, y_val,
                        epochs=200, batch_size=32, patience=15, verbose=1):
    """Train the LSTM with early stopping.

    Returns
    -------
    history : tf.keras.callbacks.History
    """
    early_stop = callbacks.EarlyStopping(
        monitor="val_loss",
        patience=patience,
        restore_best_weights=True,
    )
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stop],
        verbose=verbose,
    )
    return history


def estimate_process_noise(model, X_train, y_train):
    """Estimate process noise Q from LSTM training residuals (Type A, GUM).

    Q = sample variance of (y_true - y_pred).

    Returns
    -------
    Q : float
    """
    y_pred = model.predict(X_train, verbose=0)
    residuals = y_train - y_pred
    Q = float(np.var(residuals, ddof=1))
    return Q
