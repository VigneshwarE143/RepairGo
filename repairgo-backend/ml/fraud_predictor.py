"""
Fraud Predictor Module.

This module provides fraud score prediction functionality using the trained
Isolation Forest model, with feature contribution explainability.
"""

import os
import time
import joblib
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from database import fraud_flags_collection
from utils.logger import logger

# Path to saved models
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
FRAUD_MODEL_PATH = os.path.join(MODEL_DIR, "fraud_model.joblib")
FRAUD_SCALER_PATH = os.path.join(MODEL_DIR, "fraud_scaler.joblib")
FRAUD_FEATURE_STATS_PATH = os.path.join(MODEL_DIR, "fraud_feature_stats.joblib")

# Module state
_model = None
_scaler = None
_feature_stats = None
_model_loaded_at: Optional[datetime] = None

# Anomaly threshold
ANOMALY_THRESHOLD = -0.3


def load_fraud_model() -> Tuple[bool, Optional[str]]:
    """
    Load the trained fraud model and scaler from disk.
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    global _model, _scaler, _feature_stats, _model_loaded_at
    
    if not os.path.exists(FRAUD_MODEL_PATH):
        return False, f"Fraud model not found: {FRAUD_MODEL_PATH}"
    
    if not os.path.exists(FRAUD_SCALER_PATH):
        return False, f"Fraud scaler not found: {FRAUD_SCALER_PATH}"
    
    try:
        _model = joblib.load(FRAUD_MODEL_PATH)
        _scaler = joblib.load(FRAUD_SCALER_PATH)
        
        if os.path.exists(FRAUD_FEATURE_STATS_PATH):
            _feature_stats = joblib.load(FRAUD_FEATURE_STATS_PATH)
        
        _model_loaded_at = datetime.utcnow()
        logger.info(f"Fraud model loaded successfully at {_model_loaded_at}")
        return True, None
    except Exception as e:
        error_msg = f"Failed to load fraud model: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def is_fraud_model_available() -> bool:
    """Check if the fraud model is loaded and available."""
    return _model is not None and _scaler is not None


def get_fraud_model_info() -> Dict:
    """Get information about the currently loaded fraud model."""
    return {
        "available": is_fraud_model_available(),
        "loaded_at": _model_loaded_at.isoformat() if _model_loaded_at else None,
        "model_path": FRAUD_MODEL_PATH,
        "anomaly_threshold": ANOMALY_THRESHOLD,
        "feature_names": _feature_stats.get("feature_names", []) if _feature_stats else [],
    }


def calculate_feature_contributions(
    features: np.ndarray,
    feature_names: List[str],
) -> List[Dict]:
    """
    Calculate feature contributions to the anomaly score.
    
    Uses the deviation from mean (in std units) as a proxy for contribution.
    Higher absolute deviation = more suspicious.
    """
    if _feature_stats is None:
        return []
    
    mean = np.array(_feature_stats["mean"])
    std = np.array(_feature_stats["std"])
    
    # Calculate z-scores (deviation from mean in std units)
    z_scores = (features[0] - mean) / (std + 1e-8)
    
    contributions = []
    for i, (name, z_score) in enumerate(zip(feature_names, z_scores)):
        contributions.append({
            "feature": name,
            "value": float(features[0][i]),
            "z_score": float(z_score),
            "contribution": abs(float(z_score)),  # Higher = more anomalous
            "direction": "high" if z_score > 0 else "low",
        })
    
    # Sort by contribution (most suspicious first)
    contributions.sort(key=lambda x: x["contribution"], reverse=True)
    
    return contributions


def predict_fraud_score(
    entity_id: str,
    entity_type: str,
) -> Dict:
    """
    Predict fraud score for an entity.
    
    Args:
        entity_id: ID of the entity (technician or service)
        entity_type: "technician" or "service"
    
    Returns:
        Dictionary with fraud score and explanation:
        - anomaly_score: float (negative = more anomalous)
        - is_anomaly: bool
        - confidence: float (0-1)
        - top_contributing_features: list
        - prediction_source: "model" or "fallback"
    """
    from ml.fraud_detection import (
        extract_technician_features,
        extract_service_features,
        TECHNICIAN_FEATURE_NAMES,
        SERVICE_FEATURE_NAMES,
    )
    
    start_time = time.perf_counter()
    
    # Extract features based on entity type
    if entity_type == "technician":
        features_dict = extract_technician_features(entity_id)
        feature_names = TECHNICIAN_FEATURE_NAMES
        
        if features_dict:
            feature_vector = np.array([[
                features_dict["cancellation_rate"],
                features_dict["price_deviation_avg"],
                features_dict["job_frequency"],
                features_dict["rating_variation"],
                features_dict["completion_time_variance"],
                features_dict["avg_rating"],
            ]])
        else:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "error": "Entity not found",
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "latency_ms": round(latency_ms, 3),
            }
    
    elif entity_type == "service":
        features_dict = extract_service_features(entity_id)
        feature_names = SERVICE_FEATURE_NAMES + ["placeholder"]
        
        if features_dict:
            feature_vector = np.array([[
                features_dict["price_deviation"],
                features_dict["completion_time_ratio"],
                features_dict["rating_deviation"],
                features_dict["urgency_score"],
                features_dict["distance_score"],
                0.0,  # Placeholder for avg_rating (not applicable)
            ]])
        else:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "error": "Entity not found",
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "latency_ms": round(latency_ms, 3),
            }
    else:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "error": f"Invalid entity type: {entity_type}",
            "anomaly_score": 0.0,
            "is_anomaly": False,
            "latency_ms": round(latency_ms, 3),
        }
    
    prediction_source = "model"
    
    # Use ML model if available
    if is_fraud_model_available():
        try:
            features_scaled = _scaler.transform(feature_vector)
            anomaly_score = float(_model.decision_function(features_scaled)[0])
            prediction = _model.predict(features_scaled)[0]
            is_anomaly = prediction == -1 or anomaly_score < ANOMALY_THRESHOLD
            
            # Calculate feature contributions
            contributions = calculate_feature_contributions(
                feature_vector,
                TECHNICIAN_FEATURE_NAMES,  # Use full feature names
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                f"[Fraud] ML prediction completed in {latency_ms:.2f}ms, "
                f"score={anomaly_score:.4f}, anomaly={is_anomaly}"
            )
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                f"[Fraud] ML prediction failed in {latency_ms:.2f}ms: {e}"
            )
            anomaly_score, is_anomaly, contributions = _fallback_prediction(
                features_dict, entity_type
            )
            prediction_source = "fallback"
    else:
        anomaly_score, is_anomaly, contributions = _fallback_prediction(
            features_dict, entity_type
        )
        prediction_source = "fallback"
    
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    if prediction_source == "fallback":
        logger.debug(
            f"[Fraud] Fallback prediction completed in {latency_ms:.2f}ms, "
            f"score={anomaly_score:.4f}"
        )
    
    # Calculate confidence (distance from threshold)
    if anomaly_score < ANOMALY_THRESHOLD:
        confidence = min(1.0, abs(anomaly_score - ANOMALY_THRESHOLD) / 0.5)
    else:
        confidence = max(0.0, 1.0 - (anomaly_score - ANOMALY_THRESHOLD) / 0.5)
    
    result = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "anomaly_score": round(anomaly_score, 4),
        "is_anomaly": is_anomaly,
        "confidence": round(confidence, 3),
        "threshold": ANOMALY_THRESHOLD,
        "prediction_source": prediction_source,
        "model_available": is_fraud_model_available(),
        "features": features_dict,
        "top_contributing_features": contributions[:5],  # Top 5
        "predicted_at": datetime.utcnow().isoformat(),
        "latency_ms": round(latency_ms, 3),
    }
    
    return result


def _fallback_prediction(
    features: Dict,
    entity_type: str,
) -> Tuple[float, bool, List[Dict]]:
    """
    Rule-based fallback for fraud detection.
    
    Returns (anomaly_score, is_anomaly, contributions)
    """
    contributions = []
    risk_score = 0.0
    
    if entity_type == "technician":
        # Check cancellation rate
        cancel_rate = features.get("cancellation_rate", 0)
        if cancel_rate > 0.3:
            risk_score += 0.4
            contributions.append({
                "feature": "cancellation_rate",
                "value": cancel_rate,
                "contribution": 0.4,
                "direction": "high",
                "reason": "High cancellation rate",
            })
        
        # Check price deviation
        price_dev = abs(features.get("price_deviation_avg", 0))
        if price_dev > 0.3:
            risk_score += 0.3
            contributions.append({
                "feature": "price_deviation_avg",
                "value": price_dev,
                "contribution": 0.3,
                "direction": "high",
                "reason": "High price deviation",
            })
        
        # Check rating
        avg_rating = features.get("avg_rating", 5.0)
        if avg_rating < 2.5:
            risk_score += 0.2
            contributions.append({
                "feature": "avg_rating",
                "value": avg_rating,
                "contribution": 0.2,
                "direction": "low",
                "reason": "Low average rating",
            })
    
    elif entity_type == "service":
        # Check price deviation
        price_dev = abs(features.get("price_deviation", 0))
        if price_dev > 0.3:
            risk_score += 0.4
            contributions.append({
                "feature": "price_deviation",
                "value": price_dev,
                "contribution": 0.4,
                "direction": "high",
                "reason": "Suspicious price difference",
            })
        
        # Check completion time ratio
        time_ratio = features.get("completion_time_ratio", 1.0)
        if time_ratio < 0.3 or time_ratio > 3.0:
            risk_score += 0.3
            contributions.append({
                "feature": "completion_time_ratio",
                "value": time_ratio,
                "contribution": 0.3,
                "direction": "high" if time_ratio > 3.0 else "low",
                "reason": "Abnormal completion time",
            })
    
    # Convert risk_score (0-1) to anomaly_score format (positive = normal, negative = anomalous)
    anomaly_score = 0.2 - risk_score  # Higher risk = more negative score
    is_anomaly = risk_score > 0.5 or anomaly_score < ANOMALY_THRESHOLD
    
    contributions.sort(key=lambda x: x["contribution"], reverse=True)
    
    return anomaly_score, is_anomaly, contributions


def store_fraud_flag(
    entity_id: str,
    entity_type: str,
    prediction_result: Dict,
) -> str:
    """
    Store fraud flag in the database.
    
    Returns:
        The ID of the stored/updated document
    """
    from bson import ObjectId
    
    doc = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "anomaly_score": prediction_result["anomaly_score"],
        "is_anomaly": prediction_result["is_anomaly"],
        "confidence": prediction_result["confidence"],
        "prediction_source": prediction_result["prediction_source"],
        "top_contributing_features": prediction_result["top_contributing_features"],
        "features": prediction_result.get("features", {}),
        "flagged_at": datetime.utcnow(),
        "threshold": ANOMALY_THRESHOLD,
        "status": "pending_review" if prediction_result["is_anomaly"] else "cleared",
    }
    
    # Upsert document
    result = fraud_flags_collection.update_one(
        {"entity_id": entity_id, "entity_type": entity_type},
        {"$set": doc},
        upsert=True,
    )
    
    if prediction_result["is_anomaly"]:
        logger.log_fraud_flag(
            entity_type,
            entity_id,
            f"anomaly_score={prediction_result['anomaly_score']:.3f}",
        )
    
    return str(result.upserted_id) if result.upserted_id else entity_id


def scan_all_entities() -> Dict:
    """
    Scan all technicians and services for fraud.
    
    Returns:
        Summary of scan results
    """
    from ml.fraud_detection import extract_all_technician_features, extract_all_service_features
    
    results = {
        "technicians_scanned": 0,
        "technicians_flagged": 0,
        "services_scanned": 0,
        "services_flagged": 0,
        "newly_flagged": [],
        "scanned_at": datetime.utcnow().isoformat(),
    }
    
    # Scan technicians
    for tech in technicians_collection.find({"is_active": True}):
        tech_id = str(tech.get("_id"))
        prediction = predict_fraud_score(tech_id, "technician")
        results["technicians_scanned"] += 1
        
        if prediction.get("is_anomaly"):
            store_fraud_flag(tech_id, "technician", prediction)
            results["technicians_flagged"] += 1
            results["newly_flagged"].append({
                "entity_id": tech_id,
                "entity_type": "technician",
                "score": prediction["anomaly_score"],
            })
    
    # Scan services
    for service in services_collection.find({
        "is_active": True,
        "status": {"$in": ["completed", "rated"]},
    }):
        service_id = str(service.get("_id"))
        prediction = predict_fraud_score(service_id, "service")
        results["services_scanned"] += 1
        
        if prediction.get("is_anomaly"):
            store_fraud_flag(service_id, "service", prediction)
            results["services_flagged"] += 1
            results["newly_flagged"].append({
                "entity_id": service_id,
                "entity_type": "service",
                "score": prediction["anomaly_score"],
            })
    
    return results


# Import for technicians_collection
from database import technicians_collection, services_collection

# Try to load model on module import
_init_success, _init_error = load_fraud_model()
if not _init_success:
    logger.warning(f"Fraud model not loaded at startup: {_init_error}")
