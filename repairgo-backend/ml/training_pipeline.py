"""
Training pipeline for Technician Reliability Prediction model.

This module extracts features from historical job data and trains a classifier
to predict the probability of successful job completion.
"""

import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from database import services_collection, technicians_collection

# Path to save the trained model
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
MODEL_PATH = os.path.join(MODEL_DIR, "reliability_model.joblib")
SCALER_PATH = os.path.join(MODEL_DIR, "reliability_scaler.joblib")

# Feature names for the model
FEATURE_NAMES = [
    "avg_rating",
    "cancellation_rate",
    "avg_response_time",
    "completed_jobs",
    "current_workload",
    "distance_to_customer",
]


def ensure_model_dir() -> None:
    """Ensure the model directory exists."""
    os.makedirs(MODEL_DIR, exist_ok=True)


def calculate_response_time_minutes(service: Dict) -> Optional[float]:
    """Calculate response time from assignment to on_the_way status."""
    assigned_at = service.get("assigned_at")
    updated_at = service.get("updated_at")
    status = service.get("status")
    
    if not assigned_at or not updated_at:
        return None
    
    if status in ["on_the_way", "in_progress", "completed", "rated"]:
        if isinstance(assigned_at, datetime) and isinstance(updated_at, datetime):
            delta = (updated_at - assigned_at).total_seconds() / 60.0
            return max(0.0, delta)
    
    return None


def extract_technician_stats(technician_id: str) -> Dict:
    """Extract aggregated statistics for a technician."""
    technician = technicians_collection.find_one({"_id": technician_id})
    
    if not technician:
        return {
            "avg_rating": 0.0,
            "cancellation_rate": 0.0,
            "completed_jobs": 0,
            "current_workload": 0,
        }
    
    completed = int(technician.get("completed_jobs", 0) or 0)
    cancelled = int(technician.get("cancelled_jobs", 0) or 0)
    total_jobs = max(completed + cancelled, 1)
    
    return {
        "avg_rating": float(technician.get("rating", 0.0) or 0.0),
        "cancellation_rate": cancelled / total_jobs,
        "completed_jobs": completed,
        "current_workload": int(technician.get("workload", 0) or 0),
    }


def calculate_distance(service: Dict, technician: Dict) -> float:
    """Calculate haversine distance between service location and technician."""
    import math
    
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
    
    return radius_km * c


def extract_training_data() -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract training data from historical job records.
    
    Returns:
        Tuple of (features array, labels array)
        Label: 1 = successful completion (completed/rated), 0 = unsuccessful (cancelled)
    """
    features_list = []
    labels_list = []
    
    # Get all completed, rated, or cancelled services with assigned technicians
    historical_services = list(services_collection.find({
        "status": {"$in": ["completed", "rated", "cancelled"]},
        "technician_id": {"$exists": True, "$ne": None},
        "is_active": True,
    }))
    
    # Build technician cache for efficiency
    technician_cache = {}
    for tech in technicians_collection.find({"is_active": True}):
        technician_cache[str(tech.get("_id"))] = tech
    
    # Calculate average response times per technician
    response_times: Dict[str, List[float]] = {}
    for service in historical_services:
        tech_id = str(service.get("technician_id"))
        rt = calculate_response_time_minutes(service)
        if rt is not None:
            if tech_id not in response_times:
                response_times[tech_id] = []
            response_times[tech_id].append(rt)
    
    avg_response_times = {
        tech_id: np.mean(times) if times else 30.0
        for tech_id, times in response_times.items()
    }
    
    for service in historical_services:
        tech_id = str(service.get("technician_id"))
        technician = technician_cache.get(tech_id)
        
        if not technician:
            continue
        
        # Extract features
        stats = extract_technician_stats(tech_id)
        distance = calculate_distance(service, technician)
        avg_response_time = avg_response_times.get(tech_id, 30.0)
        
        feature_vector = [
            stats["avg_rating"],
            stats["cancellation_rate"],
            avg_response_time,
            stats["completed_jobs"],
            stats["current_workload"],
            distance,
        ]
        
        # Determine label: 1 = success, 0 = failure
        status = service.get("status")
        label = 1 if status in ["completed", "rated"] else 0
        
        features_list.append(feature_vector)
        labels_list.append(label)
    
    return np.array(features_list), np.array(labels_list)


def generate_synthetic_data(n_samples: int = 500) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data when historical data is insufficient.
    
    This creates realistic patterns based on domain knowledge:
    - Higher ratings correlate with success
    - Lower cancellation rates correlate with success
    - Shorter response times correlate with success
    - More experience (completed_jobs) correlates with success
    - Lower workload correlates with success
    - Shorter distances correlate with success
    """
    np.random.seed(42)
    
    features = []
    labels = []
    
    for _ in range(n_samples):
        # Generate features with realistic distributions
        avg_rating = np.random.uniform(2.0, 5.0)
        cancellation_rate = np.random.uniform(0.0, 0.5)
        avg_response_time = np.random.uniform(5.0, 120.0)
        completed_jobs = np.random.randint(0, 200)
        current_workload = np.random.randint(0, 10)
        distance_to_customer = np.random.uniform(0.5, 50.0)
        
        # Calculate success probability based on features
        success_prob = (
            0.3 * (avg_rating / 5.0) +
            0.25 * (1.0 - cancellation_rate * 2) +
            0.15 * (1.0 - min(avg_response_time / 120.0, 1.0)) +
            0.1 * min(completed_jobs / 100.0, 1.0) +
            0.1 * (1.0 - current_workload / 10.0) +
            0.1 * (1.0 - min(distance_to_customer / 50.0, 1.0))
        )
        
        # Add some noise and clip
        success_prob = np.clip(success_prob + np.random.normal(0, 0.1), 0.1, 0.95)
        
        # Generate label based on probability
        label = 1 if np.random.random() < success_prob else 0
        
        features.append([
            avg_rating,
            cancellation_rate,
            avg_response_time,
            completed_jobs,
            current_workload,
            distance_to_customer,
        ])
        labels.append(label)
    
    return np.array(features), np.array(labels)


def train_model(
    model_type: str = "random_forest",
    min_samples: int = 50,
    use_synthetic_if_needed: bool = True,
) -> Dict:
    """
    Train the reliability prediction model.
    
    Args:
        model_type: "random_forest" or "logistic_regression"
        min_samples: Minimum samples required for training
        use_synthetic_if_needed: Generate synthetic data if insufficient real data
    
    Returns:
        Dictionary with training metrics and model info
    """
    ensure_model_dir()
    
    # Extract historical data
    X, y = extract_training_data()
    data_source = "historical"
    
    # Check if we have enough data
    if len(X) < min_samples:
        if use_synthetic_if_needed:
            # Combine with synthetic data
            X_synthetic, y_synthetic = generate_synthetic_data(n_samples=500)
            if len(X) > 0:
                X = np.vstack([X, X_synthetic])
                y = np.concatenate([y, y_synthetic])
            else:
                X, y = X_synthetic, y_synthetic
            data_source = "synthetic" if len(X) == 500 else "mixed"
        else:
            return {
                "success": False,
                "error": f"Insufficient training data. Found {len(X)}, need {min_samples}",
            }
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Initialize model
    if model_type == "logistic_regression":
        model = LogisticRegression(
            random_state=42,
            max_iter=1000,
            class_weight="balanced",
        )
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight="balanced",
        )
    
    # Train model
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
    }
    
    # Cross-validation score
    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)
    metrics["cv_mean"] = float(np.mean(cv_scores))
    metrics["cv_std"] = float(np.std(cv_scores))
    
    # Save model and scaler
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    
    # Feature importances (for Random Forest)
    feature_importance = {}
    if hasattr(model, "feature_importances_"):
        for name, importance in zip(FEATURE_NAMES, model.feature_importances_):
            feature_importance[name] = float(importance)
    
    # Register model in model registry
    try:
        from ml.model_registry import model_registry
        
        model_doc = model_registry.register_model(
            model_name="reliability_rf",
            model_type=type(model).__name__,
            accuracy=metrics["accuracy"],
            validation_score=metrics["cv_mean"],
            feature_count=len(FEATURE_NAMES),
            feature_names=FEATURE_NAMES,
            training_samples=len(X_train),
            hyperparameters={
                "n_estimators": 100 if model_type == "random_forest" else None,
                "max_depth": 10 if model_type == "random_forest" else None,
            },
            notes=f"Data source: {data_source}",
        )
        
        # Auto-deploy as active version
        model_registry.deploy_model("reliability_rf", model_doc["version"])
        
        registry_version = model_doc["version"]
    except Exception as e:
        # Don't fail training if registry fails
        registry_version = None
    
    return {
        "success": True,
        "model_type": model_type,
        "data_source": data_source,
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "metrics": metrics,
        "feature_importance": feature_importance,
        "model_path": MODEL_PATH,
        "trained_at": datetime.utcnow().isoformat(),
        "registry_version": registry_version,
    }


def retrain_model() -> Dict:
    """Convenience function to retrain the model with default settings."""
    return train_model(model_type="random_forest", use_synthetic_if_needed=True)


if __name__ == "__main__":
    # Train model when run directly
    result = train_model()
    print("Training Result:", result)
