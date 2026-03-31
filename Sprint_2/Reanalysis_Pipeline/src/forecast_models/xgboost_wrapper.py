import numpy as np

try:
    from xgboost import XGBRegressor
    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False


class XGBoostForecastModel:
    """XGBoost wrapped in the ForecastModel interface.

    Flattens (N, lookback, 1) -> (N, lookback) for XGBoost input.
    Requires the `xgboost` package (not bundled with scikit-learn).
    """

    def __init__(self, n_estimators: int = 100, max_depth: int = 6,
                 learning_rate: float = 0.1, subsample: float = 0.8,
                 colsample_bytree: float = 0.8):
        if not _XGBOOST_AVAILABLE:
            raise ImportError(
                "xgboost is not installed. Run: pip install xgboost"
            )
        self._model = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )

    def _reshape(self, X: np.ndarray) -> np.ndarray:
        return X.reshape(X.shape[0], -1)

    def train(self, X_train, y_train, X_val, y_val, **kwargs):
        """Fit XGBoost on training data with early stopping on val set."""
        self._model.fit(
            self._reshape(X_train), y_train.ravel(),
            eval_set=[(self._reshape(X_val), y_val.ravel())],
            verbose=False,
        )

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
