"""
Fraud Detection Training Pipeline using Isolation Forest.

This module trains an anomaly detection model to identify potentially
fraudulent technicians and service requests.
"""

import os
import joblib
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from database import (
    services_collection,
    technicians_collection,
    fraud_flags_collection,
)
from utils.logger import logger

# Path to save the trained model
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
FRAUD_MODEL_PATH = os.path.join(MODEL_DIR, "fraud_model.joblib")
FRAUD_SCALER_PATH = os.path.join(MODEL_DIR, "fraud_scaler.joblib")
FRAUD_FEATURE_STATS_PATH = os.path.join(MODEL_DIR, "fraud_feature_stats.joblib")

# Feature names for explainability
TECHNICIAN_FEATURE_NAMES = [
    "cancellation_rate",
    "price_deviation_avg",
    "job_frequency",
    "rating_variation",
    "completion_time_variance",
    "avg_rating",
]

SERVICE_FEATURE_NAMES = [
    "price_deviation",
    "completion_time_ratio",
    "rating_deviation",
    "urgency_score",
    "distance_score",
]

# Anomaly threshold (scores below this are flagged)
ANOMALY_THRESHOLD = -0.3


def ensure_model_dir() -> None:
    """Ensure the model directory exists."""
    os.makedirs(MODEL_DIR, exist_ok=True)


def extract_technician_features(technician_id: str) -> Optional[Dict]:
    """
    Extract fraud detection features for a technician.
    
    Features:
    - cancellation_rate: Ratio of cancelled to total jobs
    - price_deviation_avg: Average deviation from estimated prices
    - job_frequency: Jobs per day over last 30 days
    - rating_variation: Standard deviation of ratings received
    - completion_time_variance: Variance in job completion times
    - avg_rating: Average rating
    """
    from bson import ObjectId
    
    try:
        tech_oid = ObjectId(technician_id)
    except Exception:
        return None
    
    technician = technicians_collection.find_one({"_id": tech_oid, "is_active": True})
    if not technician:
        return None
    
    # Basic stats
    completed = int(technician.get("completed_jobs", 0) or 0)
    cancelled = int(technician.get("cancelled_jobs", 0) or 0)
    total_jobs = max(completed + cancelled, 1)
    
    cancellation_rate = cancelled / total_jobs
    avg_rating = float(technician.get("rating", 0.0) or 0.0)
    
    # Get services for this technician
    cutoff = datetime.utcnow() - timedelta(days=30)
    services = list(services_collection.find({
        "technician_id": str(technician_id),
        "is_active": True,
    }))
    
    recent_services = [s for s in services if s.get("created_at", datetime.min) > cutoff]
    
    # Job frequency (jobs per day over last 30 days)
    job_frequency = len(recent_services) / 30.0
    
    # Price deviation average
    price_deviations = []
    for service in services:
        estimated = service.get("estimated_price")
        final = service.get("final_price")
        if isinstance(estimated, (int, float)) and isinstance(final, (int, float)) and estimated > 0:
            deviation = (final - estimated) / estimated
            price_deviations.append(deviation)
    
    price_deviation_avg = np.mean(price_deviations) if price_deviations else 0.0
    
    # Rating variation (std of ratings received)
    ratings = [s.get("rating") for s in services if isinstance(s.get("rating"), (int, float))]
    rating_variation = np.std(ratings) if len(ratings) > 1 else 0.0
    
    # Completion time variance
    completion_times = []
    for service in services:
        if service.get("status") in ["completed", "rated"]:
            assigned_at = service.get("assigned_at")
            updated_at = service.get("updated_at")
            if isinstance(assigned_at, datetime) and isinstance(updated_at, datetime):
                duration = (updated_at - assigned_at).total_seconds() / 60.0
                completion_times.append(duration)
    
    completion_time_variance = np.var(completion_times) if len(completion_times) > 1 else 0.0
    # Normalize to reasonable scale
    completion_time_variance = min(completion_time_variance, 10000) / 100.0
    
    return {
        "entity_id": str(technician_id),
        "entity_type": "technician",
        "cancellation_rate": cancellation_rate,
        "price_deviation_avg": price_deviation_avg,
        "job_frequency": job_frequency,
        "rating_variation": rating_variation,
        "completion_time_variance": completion_time_variance,
        "avg_rating": avg_rating,
    }


def extract_service_features(service_id: str) -> Optional[Dict]:
    """
    Extract fraud detection features for a service request.
    
    Features:
    - price_deviation: Difference between estimated and final price
    - completion_time_ratio: Actual vs expected completion time
    - rating_deviation: How far rating is from technician's average
    - urgency_score: Urgency level encoded
    - distance_score: Distance to technician (anomaly if too far)
    """
    from bson import ObjectId
    
    try:
        service_oid = ObjectId(service_id)
    except Exception:
        return None
    
    service = services_collection.find_one({"_id": service_oid, "is_active": True})
    if not service:
        return None
    
    # Price deviation
    estimated = service.get("estimated_price", 0)
    final = service.get("final_price", 0)
    if isinstance(estimated, (int, float)) and isinstance(final, (int, float)) and estimated > 0:
        price_deviation = (final - estimated) / estimated
    else:
        price_deviation = 0.0
    
    # Completion time ratio
    assigned_at = service.get("assigned_at")
    updated_at = service.get("updated_at")
    eta_minutes = service.get("eta_minutes", 30)
    
    if isinstance(assigned_at, datetime) and isinstance(updated_at, datetime):
        actual_duration = (updated_at - assigned_at).total_seconds() / 60.0
        expected_duration = max(float(eta_minutes) if eta_minutes else 30.0, 1.0)
        completion_time_ratio = actual_duration / expected_duration
    else:
        completion_time_ratio = 1.0
    
    # Rating deviation
    service_rating = service.get("rating")
    tech_id = service.get("technician_id")
    rating_deviation = 0.0
    
    if isinstance(service_rating, (int, float)) and tech_id:
        try:
            tech = technicians_collection.find_one({"_id": ObjectId(tech_id)})
            if tech:
                tech_avg_rating = float(tech.get("rating", 0) or 0)
                rating_deviation = abs(service_rating - tech_avg_rating)
        except Exception:
            pass
    
    # Urgency score
    urgency_map = {"low": 0.0, "medium": 0.5, "high": 1.0}
    urgency_score = urgency_map.get(service.get("urgency", "medium"), 0.5)
    
    # Distance score (if available)
    distance_score = 0.0
    location = service.get("location", {})
    if tech_id:
        try:
            tech = technicians_collection.find_one({"_id": ObjectId(tech_id)})
            if tech and location:
                from utils.technician_selection import haversine_distance_km
                distance = haversine_distance_km(
                    location.get("latitude", 0.0),
                    location.get("longitude", 0.0),
                    tech.get("latitude", 0.0),
                    tech.get("longitude", 0.0),
                )
                # Normalize: 50km = 1.0
                distance_score = min(distance / 50.0, 2.0)
        except Exception:
            pass
    
    return {
        "entity_id": str(service_id),
        "entity_type": "service",
        "price_deviation": price_deviation,
        "completion_time_ratio": completion_time_ratio,
        "rating_deviation": rating_deviation,
        "urgency_score": urgency_score,
        "distance_score": distance_score,
    }


def generate_synthetic_technician_data(n_samples: int = 200) -> np.ndarray:
    """Generate synthetic technician feature data for training."""
    np.random.seed(42)
    
    features = []
    
    for i in range(n_samples):
        if i < int(n_samples * 0.9):
            # Normal technicians (90%)
            cancellation_rate = np.abs(np.random.normal(0.05, 0.03))
            price_deviation_avg = np.random.normal(0.0, 0.1)
            job_frequency = np.random.uniform(0.5, 3.0)
            rating_variation = np.random.uniform(0.1, 0.5)
            completion_time_variance = np.random.uniform(1, 20)
            avg_rating = np.random.uniform(3.5, 5.0)
        else:
            # Anomalous technicians (10%)
            cancellation_rate = np.random.uniform(0.3, 0.8)
            price_deviation_avg = np.random.uniform(0.3, 1.0) * np.random.choice([-1, 1])
            job_frequency = np.random.choice([
                np.random.uniform(0.0, 0.1),  # Too few
                np.random.uniform(8.0, 15.0),  # Too many
            ])
            rating_variation = np.random.uniform(1.0, 2.5)
            completion_time_variance = np.random.uniform(50, 100)
            avg_rating = np.random.uniform(1.0, 2.5)
        
        features.append([
            cancellation_rate,
            price_deviation_avg,
            job_frequency,
            rating_variation,
            completion_time_variance,
            avg_rating,
        ])
    
    return np.array(features)


def generate_synthetic_service_data(n_samples: int = 300) -> np.ndarray:
    """Generate synthetic service feature data for training."""
    np.random.seed(42)
    
    features = []
    
    for i in range(n_samples):
        if i < int(n_samples * 0.9):
            # Normal services (90%)
            price_deviation = np.random.normal(0.0, 0.15)
            completion_time_ratio = np.random.uniform(0.8, 1.5)
            rating_deviation = np.random.uniform(0.0, 1.0)
            urgency_score = np.random.choice([0.0, 0.5, 1.0])
            distance_score = np.random.uniform(0.0, 0.6)
        else:
            # Anomalous services (10%)
            price_deviation = np.random.uniform(0.5, 2.0) * np.random.choice([-1, 1])
            completion_time_ratio = np.random.choice([
                np.random.uniform(0.1, 0.3),  # Too fast
                np.random.uniform(3.0, 10.0),  # Too slow
            ])
            rating_deviation = np.random.uniform(2.0, 4.0)
            urgency_score = np.random.choice([0.0, 0.5, 1.0])
            distance_score = np.random.uniform(1.0, 2.0)
        
        features.append([
            price_deviation,
            completion_time_ratio,
            rating_deviation,
            urgency_score,
            distance_score,
        ])
    
    return np.array(features)


def extract_all_technician_features() -> Tuple[List[Dict], np.ndarray]:
    """Extract features for all technicians."""
    feature_dicts = []
    feature_vectors = []
    
    for tech in technicians_collection.find({"is_active": True}):
        tech_id = str(tech.get("_id"))
        features = extract_technician_features(tech_id)
        if features:
            feature_dicts.append(features)
            feature_vectors.append([
                features["cancellation_rate"],
                features["price_deviation_avg"],
                features["job_frequency"],
                features["rating_variation"],
                features["completion_time_variance"],
                features["avg_rating"],
            ])
    
    return feature_dicts, np.array(feature_vectors) if feature_vectors else np.array([])


def extract_all_service_features() -> Tuple[List[Dict], np.ndarray]:
    """Extract features for all services."""
    feature_dicts = []
    feature_vectors = []
    
    for service in services_collection.find({
        "is_active": True,
        "status": {"$in": ["completed", "rated", "cancelled"]},
    }):
        service_id = str(service.get("_id"))
        features = extract_service_features(service_id)
        if features:
            feature_dicts.append(features)
            feature_vectors.append([
                features["price_deviation"],
                features["completion_time_ratio"],
                features["rating_deviation"],
                features["urgency_score"],
                features["distance_score"],
            ])
    
    return feature_dicts, np.array(feature_vectors) if feature_vectors else np.array([])


def train_fraud_model(
    contamination: float = 0.1,
    min_samples: int = 50,
    use_synthetic_if_needed: bool = True,
) -> Dict:
    """
    Train the Isolation Forest fraud detection model.
    
    Args:
        contamination: Expected proportion of anomalies (default 10%)
        min_samples: Minimum samples required for training
        use_synthetic_if_needed: Use synthetic data if insufficient real data
    
    Returns:
        Dictionary with training results
    """
    ensure_model_dir()
    
    # Extract real data
    tech_dicts, tech_features = extract_all_technician_features()
    service_dicts, service_features = extract_all_service_features()
    
    data_source = "historical"
    
    # Check if we have enough data
    total_samples = len(tech_features) + len(service_features)
    
    if total_samples < min_samples and use_synthetic_if_needed:
        logger.info(f"Insufficient data ({total_samples} samples), using synthetic data")
        
        # Generate synthetic data
        synth_tech = generate_synthetic_technician_data(200)
        synth_service = generate_synthetic_service_data(300)
        
        # Pad service features to match technician feature count (6 features)
        synth_service_padded = np.hstack([
            synth_service,
            np.zeros((len(synth_service), 1))  # Add placeholder for avg_rating
        ])
        
        # Combine
        if len(tech_features) > 0:
            all_features = np.vstack([tech_features, synth_tech])
        else:
            all_features = synth_tech
        
        data_source = "synthetic" if total_samples == 0 else "mixed"
    else:
        # Pad service features to match
        if len(service_features) > 0:
            service_features_padded = np.hstack([
                service_features,
                np.zeros((len(service_features), 1))
            ])
        else:
            service_features_padded = np.array([])
        
        if len(tech_features) > 0 and len(service_features_padded) > 0:
            all_features = np.vstack([tech_features, service_features_padded])
        elif len(tech_features) > 0:
            all_features = tech_features
        elif len(service_features_padded) > 0:
            all_features = service_features_padded
        else:
            return {
                "success": False,
                "error": "No data available for training",
            }
    
    # Scale features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(all_features)
    
    # Calculate feature statistics for explainability
    feature_stats = {
        "mean": scaler.mean_.tolist(),
        "std": scaler.scale_.tolist(),
        "feature_names": TECHNICIAN_FEATURE_NAMES,
    }
    
    # Train Isolation Forest
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        max_samples="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(features_scaled)
    
    # Get training scores
    train_scores = model.decision_function(features_scaled)
    train_predictions = model.predict(features_scaled)
    
    n_anomalies = np.sum(train_predictions == -1)
    
    # Save model, scaler, and feature stats
    joblib.dump(model, FRAUD_MODEL_PATH)
    joblib.dump(scaler, FRAUD_SCALER_PATH)
    joblib.dump(feature_stats, FRAUD_FEATURE_STATS_PATH)
    
    logger.info(f"Fraud model trained: {len(all_features)} samples, {n_anomalies} anomalies detected")
    
    return {
        "success": True,
        "data_source": data_source,
        "total_samples": len(all_features),
        "technician_samples": len(tech_features),
        "service_samples": len(service_features) if 'service_features' in dir() else 0,
        "contamination": contamination,
        "anomalies_detected": int(n_anomalies),
        "anomaly_rate": float(n_anomalies / len(all_features)),
        "score_stats": {
            "min": float(np.min(train_scores)),
            "max": float(np.max(train_scores)),
            "mean": float(np.mean(train_scores)),
            "threshold": ANOMALY_THRESHOLD,
        },
        "model_path": FRAUD_MODEL_PATH,
        "trained_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    result = train_fraud_model()
    print("Training Result:", result)
