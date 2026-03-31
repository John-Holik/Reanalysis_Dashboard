from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class ForecastModel(Protocol):
    """Interface every forecast model must satisfy.

    The filter calls predict_batch(X) where X has shape
    (n_ensemble, lookback, 1). Each model handles its own
    internal reshape. Returns shape (n_ensemble, 1).
    """

    def train(self, X_train: np.ndarray, y_train: np.ndarray,
              X_val: np.ndarray, y_val: np.ndarray, **kwargs): ...

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Fast per-timestep predict called inside the filter loop.

        Parameters
        ----------
        X : np.ndarray, shape (n_ensemble, lookback, 1)

        Returns
        -------
        np.ndarray, shape (n_ensemble, 1)
        """
        ...

    def predict_sequences(self, X: np.ndarray) -> np.ndarray:
        """Predict over a batch of sequences for Q estimation.

        Parameters
        ----------
        X : np.ndarray, shape (N, lookback, 1)

        Returns
        -------
        np.ndarray, shape (N, 1)
        """
        ...


def estimate_process_noise(model: ForecastModel,
                           X_train: np.ndarray,
                           y_train: np.ndarray) -> float:
    """Estimate process noise Q from training residuals (Type A, GUM).

    Q = sample variance of (y_true - y_pred).

    Works for any model satisfying the ForecastModel protocol.

    Returns
    -------
    Q : float
    """
    y_pred = model.predict_sequences(X_train)
    residuals = y_train - y_pred
    return float(np.var(residuals, ddof=1))
