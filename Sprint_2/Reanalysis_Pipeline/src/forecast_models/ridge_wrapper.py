import numpy as np
from sklearn.linear_model import Ridge


class RidgeForecastModel:
    """Ridge regression wrapped in the ForecastModel interface.

    Flattens (N, lookback, 1) -> (N, lookback) for sklearn input.
    Zero extra dependencies beyond scikit-learn.
    """

    def __init__(self, alpha: float = 1.0):
        self._model = Ridge(alpha=alpha)

    def _reshape(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """Fit the Ridge model on training data.

        X_val / y_val accepted for interface compatibility but unused.
        """
        self._model.fit(self._reshape(X_train), y_train.ravel())

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Predict for n_ensemble members.

        Parameters
        ----------
        X : np.ndarray, shape (n_ensemble, lookback, 1)

        Returns
        -------
        np.ndarray, shape (n_ensemble, 1)
        """
        return self._model.predict(self._reshape(X)).reshape(-1, 1)

    def predict_sequences(self, X: np.ndarray) -> np.ndarray:
        """Predict over the full training set for Q estimation.

        Parameters
        ----------
        X : np.ndarray, shape (N, lookback, 1)

        Returns
        -------
        np.ndarray, shape (N, 1)
        """
        return self._model.predict(self._reshape(X)).reshape(-1, 1)
