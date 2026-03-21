"""
Predictor module for Technician Reliability.

This module loads the trained model and provides prediction functions
for the technician selection algorithm.
"""

import os
import time
import joblib
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime

from utils.logger import logger

# Path to saved models
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
MODEL_PATH = os.path.join(MODEL_DIR, "reliability_model.joblib")
SCALER_PATH = os.path.join(MODEL_DIR, "reliability_scaler.joblib")

# Feature names for explainability
FEATURE_NAMES = [
    "avg_rating",
    "cancellation_rate",
    "avg_response_time",
    "completed_jobs",
    "current_workload",
    "distance_to_customer",
]

# Cached model and scaler
_model = None
_scaler = None
_model_loaded_at: Optional[datetime] = None
_model_version: Optional[str] = None


def load_model() -> Tuple[bool, Optional[str]]:
    """
    Load the trained model and scaler from disk.
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    global _model, _scaler, _model_loaded_at, _model_version
    
    if not os.path.exists(MODEL_PATH):
        return False, f"Model file not found: {MODEL_PATH}"
    
    if not os.path.exists(SCALER_PATH):
        return False, f"Scaler file not found: {SCALER_PATH}"
    
    try:
        _model = joblib.load(MODEL_PATH)
        _scaler = joblib.load(SCALER_PATH)
        _model_loaded_at = datetime.utcnow()
        
        # Try to get version from registry
        try:
            from ml.model_registry import model_registry
            active_model = model_registry.get_active_model("reliability_rf")
            _model_version = active_model["version"] if active_model else "unknown"
        except Exception:
            _model_version = "unknown"
        
        logger.info(f"Reliability model v{_model_version} loaded successfully at {_model_loaded_at}")
        return True, None
    except Exception as e:
        error_msg = f"Failed to load model: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def is_model_available() -> bool:
    """Check if the model is loaded and available for predictions."""
    return _model is not None and _scaler is not None


def get_model_info() -> Dict:
    """Get information about the currently loaded model."""
    feature_importance = {}
    if _model is not None and hasattr(_model, "feature_importances_"):
        for name, importance in zip(FEATURE_NAMES, _model.feature_importances_):
            feature_importance[name] = float(importance)
    
    return {
        "available": is_model_available(),
        "loaded_at": _model_loaded_at.isoformat() if _model_loaded_at else None,
        "model_path": MODEL_PATH,
        "model_type": type(_model).__name__ if _model else None,
        "model_version": _model_version,
        "feature_names": FEATURE_NAMES,
        "feature_importance": feature_importance,
    }


def predict_reliability(
    avg_rating: float,
    cancellation_rate: float,
    avg_response_time: float,
    completed_jobs: int,
    current_workload: int,
    distance_to_customer: float,
    include_explainability: bool = True,
) -> Dict:
    """
    Predict the reliability (success probability) for a technician.
    
    Args:
        avg_rating: Technician's average rating (0-5)
        cancellation_rate: Ratio of cancelled to total jobs (0-1)
        avg_response_time: Average response time in minutes
        completed_jobs: Number of completed jobs
        current_workload: Current number of active jobs
        distance_to_customer: Distance to customer in km
        include_explainability: Whether to include feature contributions
    
    Returns:
        Dictionary with prediction results:
        - success_probability: float (0-1)
        - confidence: float (0-1) - how confident the model is
        - top_features: list of top contributing features
        - prediction_source: "model" or "fallback"
        - model_version: current model version
        - model_available: bool
    """
    start_time = time.perf_counter()
    
    # Prepare feature vector
    features = np.array([[
        avg_rating,
        cancellation_rate,
        avg_response_time,
        completed_jobs,
        current_workload,
        distance_to_customer,
    ]])
    
    feature_values = {
        "avg_rating": avg_rating,
        "cancellation_rate": cancellation_rate,
        "avg_response_time": avg_response_time,
        "completed_jobs": completed_jobs,
        "current_workload": current_workload,
        "distance_to_customer": distance_to_customer,
    }
    
    # Try to use ML model
    if is_model_available():
        try:
            features_scaled = _scaler.transform(features)
            probabilities = _model.predict_proba(features_scaled)[0]
            probability = float(probabilities[1])  # Probability of success (class 1)
            
            # Calculate confidence (distance from 0.5)
            confidence = abs(probability - 0.5) * 2  # Scale 0-1
            
            # Get top contributing features
            top_features = []
            if include_explainability and hasattr(_model, "feature_importances_"):
                # Combine feature importance with actual feature values
                feature_contributions = []
                for i, (name, importance) in enumerate(zip(FEATURE_NAMES, _model.feature_importances_)):
                    # Determine if feature value is favorable
                    value = features[0, i]
                    is_favorable = _is_feature_favorable(name, value)
                    contribution = importance * (1 if is_favorable else -1)
                    feature_contributions.append({
                        "feature": name,
                        "importance": float(importance),
                        "value": float(value),
                        "favorable": is_favorable,
                        "contribution": float(contribution),
                    })
                
                # Sort by absolute contribution
                feature_contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
                top_features = feature_contributions[:3]  # Top 3
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            logger.debug(
                f"[Reliability] ML prediction completed in {latency_ms:.2f}ms, "
                f"probability={probability:.3f}, confidence={confidence:.3f}"
            )
            
            return {
                "success_probability": probability,
                "confidence": confidence,
                "top_features": top_features,
                "prediction_source": "model",
                "model_version": _model_version,
                "model_available": True,
                "latency_ms": round(latency_ms, 3),
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                f"[Reliability] Model prediction failed in {latency_ms:.2f}ms, "
                f"using fallback: {str(e)}"
            )
    
    # Fallback to rule-based scoring
    probability, confidence, top_features = calculate_fallback_probability_with_explanation(
        avg_rating=avg_rating,
        cancellation_rate=cancellation_rate,
        avg_response_time=avg_response_time,
        completed_jobs=completed_jobs,
        current_workload=current_workload,
        distance_to_customer=distance_to_customer,
    )
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    logger.debug(
        f"[Reliability] Fallback prediction completed in {latency_ms:.2f}ms, "
        f"probability={probability:.3f}"
    )
    
    return {
        "success_probability": probability,
        "confidence": confidence,
        "top_features": top_features if include_explainability else [],
        "prediction_source": "fallback",
        "model_version": None,
        "model_available": False,
        "latency_ms": round(latency_ms, 3),
    }


def _is_feature_favorable(feature_name: str, value: float) -> bool:
    """Determine if a feature value is favorable for success."""
    favorable_thresholds = {
        "avg_rating": (3.5, True),        # Higher is better
        "cancellation_rate": (0.15, False), # Lower is better
        "avg_response_time": (45, False),  # Lower is better
        "completed_jobs": (20, True),      # Higher is better
        "current_workload": (3, False),    # Lower is better
        "distance_to_customer": (15, False), # Lower is better
    }
    
    threshold, higher_is_better = favorable_thresholds.get(feature_name, (0, True))
    if higher_is_better:
        return value >= threshold
    else:
        return value <= threshold


def calculate_fallback_probability_with_explanation(
    avg_rating: float,
    cancellation_rate: float,
    avg_response_time: float,
    completed_jobs: int,
    current_workload: int,
    distance_to_customer: float,
    max_distance_km: float = 50.0,
    max_response_time: float = 120.0,
    max_workload: int = 10,
) -> Tuple[float, float, List[Dict]]:
    """
    Calculate success probability with explainability using rule-based fallback logic.
    
    Returns:
        Tuple of (probability, confidence, top_features)
    """
    # Define weights for each feature (same as rule-based formula)
    weights = {
        "avg_rating": 0.30,
        "cancellation_rate": 0.25,
        "avg_response_time": 0.15,
        "completed_jobs": 0.10,
        "current_workload": 0.10,
        "distance_to_customer": 0.10,
    }
    
    # Calculate normalized scores for each feature
    feature_scores = {
        "avg_rating": max(0.0, min(1.0, avg_rating / 5.0)),
        "cancellation_rate": max(0.0, 1.0 - (cancellation_rate * 2)),
        "avg_response_time": max(0.0, 1.0 - (avg_response_time / max_response_time)),
        "completed_jobs": min(1.0, completed_jobs / 100.0),
        "current_workload": max(0.0, 1.0 - (current_workload / max_workload)),
        "distance_to_customer": max(0.0, 1.0 - (distance_to_customer / max_distance_km)),
    }
    
    feature_values = {
        "avg_rating": avg_rating,
        "cancellation_rate": cancellation_rate,
        "avg_response_time": avg_response_time,
        "completed_jobs": completed_jobs,
        "current_workload": current_workload,
        "distance_to_customer": distance_to_customer,
    }
    
    # Calculate weighted probability
    probability = sum(
        weights[name] * feature_scores[name]
        for name in weights
    )
    probability = max(0.0, min(1.0, probability))
    
    # Calculate confidence (how close to extremes the prediction is)
    confidence = abs(probability - 0.5) * 2
    
    # Build feature contributions for explainability
    feature_contributions = []
    for name in FEATURE_NAMES:
        score = feature_scores[name]
        weight = weights[name]
        contribution = weight * score
        is_favorable = score >= 0.5  # Above average is favorable
        
        feature_contributions.append({
            "feature": name,
            "importance": weight,
            "value": float(feature_values[name]),
            "score": round(score, 3),
            "favorable": is_favorable,
            "contribution": round(contribution, 3),
        })
    
    # Sort by contribution (descending)
    feature_contributions.sort(key=lambda x: x["contribution"], reverse=True)
    top_features = feature_contributions[:3]
    
    return probability, confidence, top_features


def calculate_fallback_probability(
    avg_rating: float,
    cancellation_rate: float,
    avg_response_time: float,
    completed_jobs: int,
    current_workload: int,
    distance_to_customer: float,
    max_distance_km: float = 50.0,
    max_response_time: float = 120.0,
    max_workload: int = 10,
) -> float:
    """
    Calculate success probability using rule-based fallback logic.
    
    This mirrors the training data generation logic to provide
    consistent predictions when the ML model is unavailable.
    """
    # Normalize each feature to 0-1 range
    rating_score = max(0.0, min(1.0, avg_rating / 5.0))
    cancel_score = max(0.0, 1.0 - (cancellation_rate * 2))
    response_score = max(0.0, 1.0 - (avg_response_time / max_response_time))
    experience_score = min(1.0, completed_jobs / 100.0)
    workload_score = max(0.0, 1.0 - (current_workload / max_workload))
    distance_score = max(0.0, 1.0 - (distance_to_customer / max_distance_km))
    
    # Weighted combination
    probability = (
        0.30 * rating_score +
        0.25 * cancel_score +
        0.15 * response_score +
        0.10 * experience_score +
        0.10 * workload_score +
        0.10 * distance_score
    )
    
    return max(0.0, min(1.0, probability))


def predict_for_technician(
    technician: Dict,
    service: Dict,
    avg_response_time: float = 30.0,
) -> Dict:
    """
    Predict reliability for a technician-service pair.
    
    Args:
        technician: Technician document from database
        service: Service document from database
        avg_response_time: Average response time for this technician
    
    Returns:
        Dictionary with prediction results
    """
    import math
    
    # Extract technician stats
    completed = int(technician.get("completed_jobs", 0) or 0)
    cancelled = int(technician.get("cancelled_jobs", 0) or 0)
    total_jobs = max(completed + cancelled, 1)
    
    avg_rating = float(technician.get("rating", 0.0) or 0.0)
    cancellation_rate = cancelled / total_jobs
    current_workload = int(technician.get("workload", 0) or 0)
    
    # Calculate distance
    service_loc = service.get("location", {}) or {}
    lat1 = service_loc.get("latitude", 0.0)
    lon1 = service_loc.get("longitude", 0.0)
    lat2 = technician.get("latitude", 0.0)
    lon2 = technician.get("longitude", 0.0)
    
    radius_km = 6371.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = radius_km * c
    
    return predict_reliability(
        avg_rating=avg_rating,
        cancellation_rate=cancellation_rate,
        avg_response_time=avg_response_time,
        completed_jobs=completed,
        current_workload=current_workload,
        distance_to_customer=distance,
    )


# Try to load model on module import
_init_success, _init_error = load_model()
if not _init_success:
    logger.warning(f"Model not loaded at startup: {_init_error}")
