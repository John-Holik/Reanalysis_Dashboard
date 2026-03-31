import numpy as np
from sklearn.ensemble import RandomForestRegressor


class RandomForestForecastModel:
    """Random Forest wrapped in the ForecastModel interface.

    Flattens (N, lookback, 1) -> (N, lookback) for sklearn input.
    Parallel prediction via n_jobs=-1.
    """

    def __init__(self, n_estimators: int = 100, max_depth=None,
                 min_samples_leaf: int = 5, max_features: float = 0.7):
        self._model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            max_features=max_features,
            random_state=42,
            n_jobs=-1,
        )

    def _reshape(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """Fit the Random Forest on training data.

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
