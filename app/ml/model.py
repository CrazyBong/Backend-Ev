"""
DemandForecaster — RandomForest wrapper with joblib persistence.

Lifecycle:
  1. On first API call: model file doesn't exist → cold_start=True → WMA fallback.
  2. After admin calls POST /v1/demand/train/{station_id}: model is trained & saved.
  3. Subsequent API calls: model is loaded from disk → cold_start=False → RF prediction.
  4. Weekly scheduler: re-trains to incorporate new data (keeps model fresh).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Models saved to  <project_root>/ml_models/<station_id>.joblib
_MODELS_DIR = Path(__file__).parent.parent.parent / "ml_models"
_MIN_TRAINING_SAMPLES = 50  # Minimum rows needed before RF is meaningful

# Lazy imports — only pay the import cost when model is actually used
_rf_cls = None
_joblib = None


def _lazy_imports():
    global _rf_cls, _joblib
    if _rf_cls is None:
        from sklearn.ensemble import RandomForestRegressor  # noqa: PLC0415
        import joblib as jl  # noqa: PLC0415
        _rf_cls = RandomForestRegressor
        _joblib = jl


class DemandForecaster:
    """
    Thin wrapper around sklearn RandomForestRegressor with joblib model persistence.
    Thread-safe for reading (predict); training is single-threaded via background job.
    """

    FEATURE_COLS = ["hour", "day_of_week", "month", "is_weekend"]

    def __init__(self, station_id: str):
        import uuid
        try:
            uuid.UUID(station_id)
        except ValueError:
            raise ValueError(f"Invalid station ID format: {station_id}")
            
        self.station_id = station_id
        self._model_path = _MODELS_DIR / f"{station_id}.joblib"
        self._model = None
        self.cold_start: bool = True  # True until model is loaded/trained

    def _ensure_dir(self) -> None:
        _MODELS_DIR.mkdir(parents=True, exist_ok=True)

    def model_exists(self) -> bool:
        return self._model_path.exists()

    def load(self) -> bool:
        """Load model from disk. Returns True if successful."""
        _lazy_imports()
        if not self.model_exists():
            return False
        try:
            self._model = _joblib.load(self._model_path)
            self.cold_start = False
            logger.info("Loaded RF model", extra={"station_id": self.station_id})
            return True
        except Exception as exc:
            logger.warning("Failed to load RF model, using WMA fallback",
                           extra={"station_id": self.station_id, "error": str(exc)})
            return False

    def train(self, X, y) -> None:
        """Train on feature matrix X and target vector y, then persist."""
        _lazy_imports()
        self._ensure_dir()
        model = _rf_cls(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,  # use all CPU cores
        )
        model.fit(X, y)
        _joblib.dump(model, self._model_path)
        self._model = model
        self.cold_start = False
        logger.info("RF model trained & saved",
                    extra={"station_id": self.station_id, "samples": len(y)})

    def predict_24h(self) -> list[dict]:
        """
        Returns 24-element list (one per hour) with predicted_bookings.
        MUST call load() or train() first; raises RuntimeError if cold_start.
        """
        if self.cold_start or self._model is None:
            raise RuntimeError("Model not ready — cold_start is True")

        from app.ml.feature_engineering import build_inference_grid  # noqa: PLC0415
        grid = build_inference_grid()
        X = grid[self.FEATURE_COLS]
        preds = self._model.predict(X)
        return [
            {"hour": int(hour), "predicted_bookings": max(0.0, round(float(pred), 2))}
            for hour, pred in zip(grid["hour"], preds)
        ]

    @classmethod
    def has_enough_data(cls, n_rows: int) -> bool:
        return n_rows >= _MIN_TRAINING_SAMPLES
