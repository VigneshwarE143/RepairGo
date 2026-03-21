"""
Demand Forecasting ML Module.

This module collects historical request data, trains a time series model,
and predicts future demand levels for dynamic pricing.
"""

import os
import joblib
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from enum import Enum

from database import services_collection
from utils.logger import logger

# Path to save the trained model
MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
DEMAND_MODEL_PATH = os.path.join(MODEL_DIR, "demand_model.joblib")
DEMAND_SCALER_PATH = os.path.join(MODEL_DIR, "demand_scaler.joblib")


class DemandLevel(str, Enum):
    """Demand level classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


# Thresholds for demand classification (requests per hour)
LOW_DEMAND_THRESHOLD = 5
HIGH_DEMAND_THRESHOLD = 15


def ensure_model_dir() -> None:
    """Ensure the model directory exists."""
    os.makedirs(MODEL_DIR, exist_ok=True)


def extract_hourly_request_counts(days_back: int = 90) -> Dict[str, List[int]]:
    """
    Extract hourly request counts from historical data.
    
    Returns:
        Dictionary with keys 'timestamps' and 'counts'
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    
    # Aggregate requests by hour
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "is_active": True}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"},
                    "hour": {"$hour": "$created_at"},
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1, "_id.hour": 1}},
    ]
    
    results = list(services_collection.aggregate(pipeline))
    
    timestamps = []
    counts = []
    
    for doc in results:
        ts = datetime(
            doc["_id"]["year"],
            doc["_id"]["month"],
            doc["_id"]["day"],
            doc["_id"]["hour"],
        )
        timestamps.append(ts)
        counts.append(doc["count"])
    
    return {"timestamps": timestamps, "counts": counts}


def extract_features_from_datetime(dt: datetime) -> np.ndarray:
    """
    Extract time-based features from a datetime object.
    
    Features:
    - hour_sin, hour_cos (cyclical encoding of hour)
    - day_sin, day_cos (cyclical encoding of day of week)
    - is_weekend
    - month_sin, month_cos (cyclical encoding of month)
    """
    hour = dt.hour
    day_of_week = dt.weekday()
    month = dt.month
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    
    # Cyclical encoding
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    day_sin = np.sin(2 * np.pi * day_of_week / 7)
    day_cos = np.cos(2 * np.pi * day_of_week / 7)
    month_sin = np.sin(2 * np.pi * (month - 1) / 12)
    month_cos = np.cos(2 * np.pi * (month - 1) / 12)
    
    return np.array([
        hour_sin, hour_cos,
        day_sin, day_cos,
        is_weekend,
        month_sin, month_cos,
    ])


def generate_synthetic_demand_data(n_days: int = 90) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic demand data when historical data is insufficient.
    
    Creates realistic patterns:
    - Higher demand during business hours (9 AM - 6 PM)
    - Lower demand on weekends
    - Seasonal variations
    """
    np.random.seed(42)
    
    features_list = []
    demand_list = []
    
    start_date = datetime.utcnow() - timedelta(days=n_days)
    
    for day in range(n_days):
        for hour in range(24):
            dt = start_date + timedelta(days=day, hours=hour)
            features = extract_features_from_datetime(dt)
            
            # Base demand
            base_demand = 10
            
            # Hour effect: peak during business hours
            if 9 <= hour <= 18:
                hour_effect = 5 + np.random.normal(0, 2)
            elif 6 <= hour <= 21:
                hour_effect = 2 + np.random.normal(0, 1)
            else:
                hour_effect = -3 + np.random.normal(0, 1)
            
            # Weekend effect: lower demand
            is_weekend = dt.weekday() >= 5
            weekend_effect = -3 if is_weekend else 0
            
            # Seasonal effect
            month = dt.month
            if month in [6, 7, 8]:  # Summer - higher HVAC demand
                seasonal_effect = 3
            elif month in [12, 1, 2]:  # Winter - higher heating demand
                seasonal_effect = 2
            else:
                seasonal_effect = 0
            
            # Random noise
            noise = np.random.normal(0, 2)
            
            demand = base_demand + hour_effect + weekend_effect + seasonal_effect + noise
            demand = max(0, int(round(demand)))
            
            features_list.append(features)
            demand_list.append(demand)
    
    return np.array(features_list), np.array(demand_list)


def train_demand_model(min_data_points: int = 168) -> Dict:
    """
    Train the demand forecasting model.
    
    Uses a Random Forest Regressor for demand prediction based on
    time-based features. Falls back to synthetic data if insufficient
    historical data.
    
    Args:
        min_data_points: Minimum hourly data points required (168 = 1 week)
    
    Returns:
        Dictionary with training results and metrics
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    
    ensure_model_dir()
    
    # Extract historical data
    historical = extract_hourly_request_counts(days_back=90)
    timestamps = historical["timestamps"]
    counts = historical["counts"]
    
    data_source = "historical"
    
    if len(timestamps) < min_data_points:
        logger.info(f"Insufficient historical data ({len(timestamps)} points), using synthetic data")
        X, y = generate_synthetic_demand_data(n_days=90)
        data_source = "synthetic"
    else:
        # Extract features from timestamps
        X = np.array([extract_features_from_datetime(ts) for ts in timestamps])
        y = np.array(counts)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    
    metrics = {
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2_score": float(r2_score(y_test, y_pred)),
    }
    
    # Feature importance
    feature_names = [
        "hour_sin", "hour_cos",
        "day_sin", "day_cos",
        "is_weekend",
        "month_sin", "month_cos",
    ]
    feature_importance = {
        name: float(imp)
        for name, imp in zip(feature_names, model.feature_importances_)
    }
    
    # Save model and scaler
    joblib.dump(model, DEMAND_MODEL_PATH)
    joblib.dump(scaler, DEMAND_SCALER_PATH)
    
    logger.info(f"Demand model trained: MAE={metrics['mae']:.2f}, R2={metrics['r2_score']:.2f}")
    
    return {
        "success": True,
        "data_source": data_source,
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "metrics": metrics,
        "feature_importance": feature_importance,
        "model_path": DEMAND_MODEL_PATH,
        "trained_at": datetime.utcnow().isoformat(),
    }


def classify_demand(predicted_count: float) -> DemandLevel:
    """
    Classify predicted demand into Low/Normal/High.
    
    Args:
        predicted_count: Predicted number of requests per hour
    
    Returns:
        DemandLevel enum value
    """
    if predicted_count < LOW_DEMAND_THRESHOLD:
        return DemandLevel.LOW
    elif predicted_count > HIGH_DEMAND_THRESHOLD:
        return DemandLevel.HIGH
    else:
        return DemandLevel.NORMAL


def get_demand_multiplier(demand_level: DemandLevel) -> float:
    """
    Get the pricing multiplier for a demand level.
    
    Returns:
        - 0.9 for low demand (discount)
        - 1.0 for normal demand
        - 1.2 for high demand (surge)
    """
    multipliers = {
        DemandLevel.LOW: 0.9,
        DemandLevel.NORMAL: 1.0,
        DemandLevel.HIGH: 1.2,
    }
    return multipliers.get(demand_level, 1.0)


if __name__ == "__main__":
    result = train_demand_model()
    print("Training Result:", result)
