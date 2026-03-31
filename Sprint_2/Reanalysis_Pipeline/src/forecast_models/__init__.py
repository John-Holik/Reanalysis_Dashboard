from .base import ForecastModel, estimate_process_noise
from .lstm_wrapper import LSTMForecastModel
from .rf_wrapper import RandomForestForecastModel
from .ridge_wrapper import RidgeForecastModel
from .xgboost_wrapper import XGBoostForecastModel

MODEL_REGISTRY = {
    "lstm":          LSTMForecastModel,
    "xgboost":       XGBoostForecastModel,
    "random_forest": RandomForestForecastModel,
    "ridge":         RidgeForecastModel,
}


def build_model(model_type: str, hyperparams: dict) -> ForecastModel:
    """Construct the appropriate forecast model from hyperparams.

    Parameters
    ----------
    model_type : str
        One of 'lstm', 'xgboost', 'random_forest', 'ridge'.
    hyperparams : dict
        Full hyperparams dict — each wrapper reads only its relevant keys.

    Returns
    -------
    ForecastModel
    """
    if model_type not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model_type '{model_type}'. "
            f"Choose from: {list(MODEL_REGISTRY)}"
        )

    if model_type == "lstm":
        return LSTMForecastModel(
            lookback=hyperparams["lookback"],
            lstm_units=hyperparams.get("lstm_units", 64),
            dense_units=hyperparams.get("dense_units", 64),
            lr=hyperparams.get("learning_rate", 0.001),
        )
    elif model_type == "xgboost":
        return XGBoostForecastModel(
            n_estimators=hyperparams.get("n_estimators", 100),
            max_depth=hyperparams.get("max_depth", 6),
            learning_rate=hyperparams.get("xgb_learning_rate", 0.1),
            subsample=hyperparams.get("subsample", 0.8),
            colsample_bytree=hyperparams.get("colsample_bytree", 0.8),
        )
    elif model_type == "random_forest":
        max_depth = hyperparams.get("max_depth_rf", None)
        return RandomForestForecastModel(
            n_estimators=hyperparams.get("n_estimators", 100),
            max_depth=max_depth if max_depth else None,
            min_samples_leaf=hyperparams.get("min_samples_leaf", 5),
            max_features=hyperparams.get("max_features", 0.7),
        )
    elif model_type == "ridge":
        return RidgeForecastModel(
            alpha=hyperparams.get("alpha", 1.0),
        )


def train_model(model: ForecastModel, X_train, y_train, X_val, y_val,
                hyperparams: dict, model_type: str):
    """Call model.train() with the correct kwargs per model type.

    Parameters
    ----------
    model : ForecastModel
    X_train, y_train, X_val, y_val : np.ndarray
    hyperparams : dict
    model_type : str

    Returns
    -------
    Training result (History for LSTM, None for sklearn models).
    """
    if model_type == "lstm":
        return model.train(
            X_train, y_train, X_val, y_val,
            epochs=hyperparams.get("epochs", 200),
            batch_size=hyperparams.get("batch_size", 32),
            patience=hyperparams.get("patience", 15),
            verbose=0,
        )
    else:
        return model.train(X_train, y_train, X_val, y_val)
