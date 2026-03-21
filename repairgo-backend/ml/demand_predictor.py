"""
Demand Predictor with Caching.

This module provides demand prediction functionality with a 10-minute cache
to reduce computation overhead.
"""

import os
import time
import joblib
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from threading import Lock

from utils.logger import logger

# Path to saved models
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
DEMAND_MODEL_PATH = os.path.join(MODEL_DIR, "demand_model.joblib")
DEMAND_SCALER_PATH = os.path.join(MODEL_DIR, "demand_scaler.joblib")

# Cache settings
CACHE_DURATION_MINUTES = 10

# Module state
_model = None
_scaler = None
_model_loaded_at: Optional[datetime] = None

# Prediction cache
_cache: Dict[str, Dict] = {}
_cache_lock = Lock()


def load_demand_model() -> Tuple[bool, Optional[str]]:
    """
    Load the trained demand model and scaler from disk.
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    global _model, _scaler, _model_loaded_at
    
    if not os.path.exists(DEMAND_MODEL_PATH):
        return False, f"Demand model not found: {DEMAND_MODEL_PATH}"
    
    if not os.path.exists(DEMAND_SCALER_PATH):
        return False, f"Demand scaler not found: {DEMAND_SCALER_PATH}"
    
    try:
        _model = joblib.load(DEMAND_MODEL_PATH)
        _scaler = joblib.load(DEMAND_SCALER_PATH)
        _model_loaded_at = datetime.utcnow()
        logger.info(f"Demand model loaded successfully at {_model_loaded_at}")
        return True, None
    except Exception as e:
        error_msg = f"Failed to load demand model: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def is_demand_model_available() -> bool:
    """Check if the demand model is loaded and available."""
    return _model is not None and _scaler is not None


def get_demand_model_info() -> Dict:
    """Get information about the currently loaded demand model."""
    return {
        "available": is_demand_model_available(),
        "loaded_at": _model_loaded_at.isoformat() if _model_loaded_at else None,
        "model_path": DEMAND_MODEL_PATH,
        "model_type": type(_model).__name__ if _model else None,
        "cache_duration_minutes": CACHE_DURATION_MINUTES,
    }


def _get_cache_key(target_time: datetime) -> str:
    """Generate a cache key for a specific hour."""
    return target_time.strftime("%Y-%m-%d-%H")


def _is_cache_valid(cache_entry: Dict) -> bool:
    """Check if a cache entry is still valid (within 10 minutes)."""
    cached_at = cache_entry.get("cached_at")
    if not cached_at:
        return False
    
    age = datetime.utcnow() - cached_at
    return age < timedelta(minutes=CACHE_DURATION_MINUTES)


def _extract_features(dt: datetime) -> np.ndarray:
    """Extract time-based features from a datetime object."""
    hour = dt.hour
    day_of_week = dt.weekday()
    month = dt.month
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    day_sin = np.sin(2 * np.pi * day_of_week / 7)
    day_cos = np.cos(2 * np.pi * day_of_week / 7)
    month_sin = np.sin(2 * np.pi * (month - 1) / 12)
    month_cos = np.cos(2 * np.pi * (month - 1) / 12)
    
    return np.array([[
        hour_sin, hour_cos,
        day_sin, day_cos,
        is_weekend,
        month_sin, month_cos,
    ]])


def predict_demand(
    target_time: Optional[datetime] = None,
    use_cache: bool = True,
) -> Dict:
    """
    Predict demand for a specific time.
    
    Args:
        target_time: The datetime to predict demand for (defaults to next hour)
        use_cache: Whether to use cached predictions (default: True)
    
    Returns:
        Dictionary with prediction results:
        - predicted_count: float (predicted requests per hour)
        - demand_level: "low", "normal", or "high"
        - multiplier: pricing multiplier (0.9, 1.0, or 1.2)
        - prediction_source: "model", "fallback", or "cache"
        - cached: bool
        - target_time: ISO format datetime
    """
    from ml.demand_forecasting import (
        classify_demand,
        get_demand_multiplier,
        DemandLevel,
        LOW_DEMAND_THRESHOLD,
        HIGH_DEMAND_THRESHOLD,
    )
    
    # Default to next hour
    if target_time is None:
        now = datetime.utcnow()
        target_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    cache_key = _get_cache_key(target_time)
    
    # Check cache
    if use_cache:
        with _cache_lock:
            if cache_key in _cache and _is_cache_valid(_cache[cache_key]):
                cached_result = _cache[cache_key].copy()
                cached_result["from_cache"] = True
                logger.debug(f"Demand prediction cache hit for {cache_key}")
                return cached_result
    
    # Make prediction
    result = _make_prediction(target_time)
    
    # Update cache
    if use_cache:
        with _cache_lock:
            result["cached_at"] = datetime.utcnow()
            _cache[cache_key] = result.copy()
            
            # Clean old cache entries
            _clean_cache()
    
    result["from_cache"] = False
    return result


def _make_prediction(target_time: datetime) -> Dict:
    """Make a demand prediction using the ML model or fallback."""
    from ml.demand_forecasting import (
        classify_demand,
        get_demand_multiplier,
        DemandLevel,
    )
    
    start_time = time.perf_counter()
    prediction_source = "model"
    
    if is_demand_model_available():
        try:
            features = _extract_features(target_time)
            features_scaled = _scaler.transform(features)
            predicted_count = float(_model.predict(features_scaled)[0])
            predicted_count = max(0, predicted_count)
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            logger.debug(
                f"[Demand] ML prediction completed in {latency_ms:.2f}ms, "
                f"count={predicted_count:.2f}"
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                f"[Demand] ML prediction failed in {latency_ms:.2f}ms: {e}"
            )
            predicted_count = _fallback_prediction(target_time)
            prediction_source = "fallback"
    else:
        predicted_count = _fallback_prediction(target_time)
        prediction_source = "fallback"
    
    latency_ms = (time.perf_counter() - start_time) * 1000
    demand_level = classify_demand(predicted_count)
    multiplier = get_demand_multiplier(demand_level)
    
    if prediction_source == "fallback":
        logger.debug(
            f"[Demand] Fallback prediction completed in {latency_ms:.2f}ms, "
            f"count={predicted_count:.2f}"
        )
    
    return {
        "predicted_count": round(predicted_count, 2),
        "demand_level": demand_level.value,
        "multiplier": multiplier,
        "prediction_source": prediction_source,
        "model_available": is_demand_model_available(),
        "target_time": target_time.isoformat(),
        "latency_ms": round(latency_ms, 3),
    }


def _fallback_prediction(target_time: datetime) -> float:
    """
    Rule-based fallback for demand prediction.
    
    Uses time-of-day and day-of-week patterns.
    """
    hour = target_time.hour
    day_of_week = target_time.weekday()
    is_weekend = day_of_week >= 5
    
    # Base demand
    base = 10
    
    # Hour-based adjustment
    if 9 <= hour <= 18:  # Business hours
        hour_adj = 5
    elif 6 <= hour <= 21:  # Extended hours
        hour_adj = 2
    else:  # Night hours
        hour_adj = -3
    
    # Weekend adjustment
    weekend_adj = -3 if is_weekend else 0
    
    return max(0, base + hour_adj + weekend_adj)


def _clean_cache() -> None:
    """Remove expired cache entries."""
    now = datetime.utcnow()
    expired_keys = [
        key for key, entry in _cache.items()
        if not _is_cache_valid(entry)
    ]
    for key in expired_keys:
        del _cache[key]


def clear_cache() -> int:
    """
    Clear all cached predictions.
    
    Returns:
        Number of entries cleared
    """
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
        return count


def get_cache_stats() -> Dict:
    """Get statistics about the prediction cache."""
    with _cache_lock:
        valid_entries = sum(1 for entry in _cache.values() if _is_cache_valid(entry))
        return {
            "total_entries": len(_cache),
            "valid_entries": valid_entries,
            "expired_entries": len(_cache) - valid_entries,
            "cache_duration_minutes": CACHE_DURATION_MINUTES,
        }


def predict_demand_range(
    start_time: datetime,
    hours: int = 24,
) -> List[Dict]:
    """
    Predict demand for a range of hours.
    
    Args:
        start_time: Start datetime
        hours: Number of hours to predict
    
    Returns:
        List of prediction results for each hour
    """
    predictions = []
    current_time = start_time.replace(minute=0, second=0, microsecond=0)
    
    for i in range(hours):
        target_time = current_time + timedelta(hours=i)
        prediction = predict_demand(target_time=target_time, use_cache=True)
        predictions.append(prediction)
    
    return predictions


# Try to load model on module import
_init_success, _init_error = load_demand_model()
if not _init_success:
    logger.warning(f"Demand model not loaded at startup: {_init_error}")
