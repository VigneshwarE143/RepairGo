"""
ML Routes for the RepairGo Backend.

Provides endpoints for:
- Predicting technician reliability
- Training/retraining the model
- Getting model status
"""

import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from utils.auth_utils import require_roles
from utils.response_utils import success_response
from utils.logger import logger

router = APIRouter(prefix="/ml", tags=["Machine Learning"])

# Timeout settings (in seconds)
PREDICTION_TIMEOUT = 5.0  # For prediction endpoints
TRAINING_TIMEOUT = 300.0  # For training endpoints (5 minutes)
SCAN_TIMEOUT = 60.0  # For scanning endpoints


class ReliabilityPredictionRequest(BaseModel):
    """Request model for reliability prediction."""
    avg_rating: float = Field(ge=0, le=5, description="Technician average rating")
    cancellation_rate: float = Field(ge=0, le=1, description="Cancellation rate (0-1)")
    avg_response_time: float = Field(ge=0, description="Average response time in minutes")
    completed_jobs: int = Field(ge=0, description="Number of completed jobs")
    current_workload: int = Field(ge=0, description="Current number of active jobs")
    distance_to_customer: float = Field(ge=0, description="Distance to customer in km")


class TrainModelRequest(BaseModel):
    """Request model for training the ML model."""
    model_type: str = Field(default="random_forest", pattern="^(random_forest|logistic_regression)$")
    min_samples: int = Field(default=50, ge=10)
    use_synthetic_if_needed: bool = Field(default=True)


@router.post("/predict-reliability")
def predict_reliability_endpoint(
    payload: ReliabilityPredictionRequest,
    user=Depends(require_roles("admin", "technician")),
):
    """
    Predict the probability of successful job completion for a technician.
    
    Returns a success probability between 0 and 1.
    Uses ML model if available, otherwise falls back to rule-based scoring.
    Includes timeout protection (5s) to ensure system stability.
    """
    from ml.predictor import predict_reliability, calculate_fallback_probability
    
    start_time = time.perf_counter()
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                predict_reliability,
                avg_rating=payload.avg_rating,
                cancellation_rate=payload.cancellation_rate,
                avg_response_time=payload.avg_response_time,
                completed_jobs=payload.completed_jobs,
                current_workload=payload.current_workload,
                distance_to_customer=payload.distance_to_customer,
            )
            try:
                result = future.result(timeout=PREDICTION_TIMEOUT)
            except FuturesTimeoutError:
                # Fallback on timeout
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Reliability prediction timed out after {PREDICTION_TIMEOUT}s, "
                    f"using fallback"
                )
                
                probability = calculate_fallback_probability(
                    avg_rating=payload.avg_rating,
                    cancellation_rate=payload.cancellation_rate,
                    avg_response_time=payload.avg_response_time,
                    completed_jobs=payload.completed_jobs,
                    current_workload=payload.current_workload,
                    distance_to_customer=payload.distance_to_customer,
                )
                
                result = {
                    "success_probability": probability,
                    "prediction_source": "fallback_timeout",
                    "model_available": False,
                    "latency_ms": round(latency_ms, 3),
                    "timed_out": True,
                }
    except Exception as e:
        # Unexpected error - use fallback
        from ml.predictor import calculate_fallback_probability
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Reliability prediction error: {e}")
        
        probability = calculate_fallback_probability(
            avg_rating=payload.avg_rating,
            cancellation_rate=payload.cancellation_rate,
            avg_response_time=payload.avg_response_time,
            completed_jobs=payload.completed_jobs,
            current_workload=payload.current_workload,
            distance_to_customer=payload.distance_to_customer,
        )
        
        result = {
            "success_probability": probability,
            "prediction_source": "fallback_error",
            "model_available": False,
            "latency_ms": round(latency_ms, 3),
            "error": str(e),
        }
    
    logger.info(
        f"Reliability prediction: prob={result['success_probability']:.3f}, "
        f"source={result['prediction_source']}, latency={result.get('latency_ms', 0):.2f}ms"
    )
    
    return success_response("Reliability prediction", result)


@router.get("/model-status")
def get_model_status(user=Depends(require_roles("admin"))):
    """
    Get the current status of the reliability prediction model.
    """
    from ml.predictor import get_model_info
    
    info = get_model_info()
    return success_response("Model status", info)


@router.post("/reload-model")
def reload_model_endpoint(user=Depends(require_roles("admin"))):
    """
    Reload the model from disk.
    
    Use this after retraining to load the new model.
    """
    from ml.predictor import load_model, get_model_info
    
    success, error = load_model()
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to reload model: {error}")
    
    logger.info(f"Admin {user.get('_id')} reloaded the ML model")
    return success_response("Model reloaded", get_model_info())


@router.post("/train")
def train_model_endpoint(
    payload: TrainModelRequest,
    user=Depends(require_roles("admin")),
):
    """
    Train or retrain the reliability prediction model.
    
    This will:
    1. Extract features from historical job data
    2. Train a new model
    3. Save it to disk
    
    Note: You need to call /ml/reload-model after training to use the new model.
    """
    from ml.training_pipeline import train_model
    
    logger.info(
        f"Admin {user.get('_id')} initiated model training: "
        f"type={payload.model_type}, min_samples={payload.min_samples}"
    )
    
    result = train_model(
        model_type=payload.model_type,
        min_samples=payload.min_samples,
        use_synthetic_if_needed=payload.use_synthetic_if_needed,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Training failed"),
        )
    
    logger.info(f"Model training completed: {result.get('metrics')}")
    return success_response("Model trained successfully", result)


@router.post("/train-and-reload")
def train_and_reload_endpoint(
    payload: Optional[TrainModelRequest] = None,
    user=Depends(require_roles("admin")),
):
    """
    Train a new model and immediately reload it.
    
    Convenience endpoint that combines /train and /reload-model.
    """
    from ml.training_pipeline import train_model
    from ml.predictor import load_model, get_model_info
    
    # Use defaults if no payload
    if payload is None:
        payload = TrainModelRequest()
    
    logger.info(f"Admin {user.get('_id')} initiated train-and-reload")
    
    # Train
    train_result = train_model(
        model_type=payload.model_type,
        min_samples=payload.min_samples,
        use_synthetic_if_needed=payload.use_synthetic_if_needed,
    )
    
    if not train_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=train_result.get("error", "Training failed"),
        )
    
    # Reload
    success, error = load_model()
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Training succeeded but reload failed: {error}",
        )
    
    return success_response(
        "Model trained and reloaded",
        {
            "training": train_result,
            "model_info": get_model_info(),
        },
    )


# ============================================================================
# Demand Forecasting Endpoints
# ============================================================================

class DemandPredictionRequest(BaseModel):
    """Request model for demand prediction."""
    target_time: Optional[str] = Field(
        default=None,
        description="ISO format datetime to predict demand for (defaults to next hour)"
    )
    use_cache: bool = Field(default=True, description="Whether to use cached predictions")


class DemandTrainRequest(BaseModel):
    """Request model for training the demand model."""
    min_data_points: int = Field(default=168, ge=24, description="Minimum hourly data points")


@router.post("/predict-demand")
def predict_demand_endpoint(
    payload: Optional[DemandPredictionRequest] = None,
    user=Depends(require_roles("admin", "customer")),
):
    """
    Predict demand level for pricing.
    
    Returns:
    - predicted_count: Expected number of requests per hour
    - demand_level: "low", "normal", or "high"
    - multiplier: Pricing multiplier (0.9, 1.0, or 1.2)
    
    Predictions are cached for 10 minutes to reduce computation.
    Includes timeout protection (5s) to ensure system stability.
    """
    from ml.demand_predictor import predict_demand, _fallback_prediction
    from ml.demand_forecasting import classify_demand, get_demand_multiplier
    from datetime import datetime
    
    start_time = time.perf_counter()
    target_time = None
    use_cache = True
    
    if payload:
        use_cache = payload.use_cache
        if payload.target_time:
            try:
                target_time = datetime.fromisoformat(payload.target_time)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                )
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                predict_demand,
                target_time=target_time,
                use_cache=use_cache,
            )
            try:
                result = future.result(timeout=PREDICTION_TIMEOUT)
            except FuturesTimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Demand prediction timed out after {PREDICTION_TIMEOUT}s, using fallback"
                )
                
                # Use fallback
                if target_time is None:
                    target_time = datetime.utcnow()
                predicted_count = _fallback_prediction(target_time)
                demand_level = classify_demand(predicted_count)
                multiplier = get_demand_multiplier(demand_level)
                
                result = {
                    "predicted_count": round(predicted_count, 2),
                    "demand_level": demand_level.value,
                    "multiplier": multiplier,
                    "prediction_source": "fallback_timeout",
                    "model_available": False,
                    "target_time": target_time.isoformat(),
                    "latency_ms": round(latency_ms, 3),
                    "timed_out": True,
                }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Demand prediction error: {e}")
        
        # Default to normal demand
        result = {
            "predicted_count": 10.0,
            "demand_level": "normal",
            "multiplier": 1.0,
            "prediction_source": "fallback_error",
            "model_available": False,
            "latency_ms": round(latency_ms, 3),
            "error": str(e),
        }
    
    logger.info(
        f"Demand prediction: level={result['demand_level']}, "
        f"multiplier={result['multiplier']}, source={result.get('prediction_source', 'unknown')}"
    )
    
    return success_response("Demand prediction", result)


@router.get("/demand-model-status")
def get_demand_model_status(user=Depends(require_roles("admin"))):
    """
    Get the current status of the demand forecasting model.
    """
    from ml.demand_predictor import get_demand_model_info, get_cache_stats
    
    model_info = get_demand_model_info()
    cache_stats = get_cache_stats()
    
    return success_response("Demand model status", {
        "model": model_info,
        "cache": cache_stats,
    })


@router.post("/train-demand")
def train_demand_model_endpoint(
    payload: Optional[DemandTrainRequest] = None,
    user=Depends(require_roles("admin")),
):
    """
    Train the demand forecasting model.
    
    Uses historical request data or synthetic data if insufficient history.
    """
    from ml.demand_forecasting import train_demand_model
    
    min_data_points = 168
    if payload:
        min_data_points = payload.min_data_points
    
    logger.info(f"Admin {user.get('_id')} initiated demand model training")
    
    result = train_demand_model(min_data_points=min_data_points)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Demand model training failed"),
        )
    
    logger.info(f"Demand model training completed: {result.get('metrics')}")
    return success_response("Demand model trained successfully", result)


@router.post("/reload-demand-model")
def reload_demand_model_endpoint(user=Depends(require_roles("admin"))):
    """
    Reload the demand model from disk.
    """
    from ml.demand_predictor import load_demand_model, get_demand_model_info
    
    success, error = load_demand_model()
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to reload demand model: {error}")
    
    logger.info(f"Admin {user.get('_id')} reloaded the demand model")
    return success_response("Demand model reloaded", get_demand_model_info())


@router.post("/train-demand-and-reload")
def train_demand_and_reload_endpoint(
    payload: Optional[DemandTrainRequest] = None,
    user=Depends(require_roles("admin")),
):
    """
    Train a new demand model and immediately reload it.
    """
    from ml.demand_forecasting import train_demand_model
    from ml.demand_predictor import load_demand_model, get_demand_model_info
    
    min_data_points = 168
    if payload:
        min_data_points = payload.min_data_points
    
    logger.info(f"Admin {user.get('_id')} initiated demand train-and-reload")
    
    # Train
    train_result = train_demand_model(min_data_points=min_data_points)
    
    if not train_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=train_result.get("error", "Training failed"),
        )
    
    # Reload
    success, error = load_demand_model()
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Training succeeded but reload failed: {error}",
        )
    
    return success_response(
        "Demand model trained and reloaded",
        {
            "training": train_result,
            "model_info": get_demand_model_info(),
        },
    )


@router.post("/clear-demand-cache")
def clear_demand_cache_endpoint(user=Depends(require_roles("admin"))):
    """
    Clear the demand prediction cache.
    """
    from ml.demand_predictor import clear_cache, get_cache_stats
    
    cleared = clear_cache()
    logger.info(f"Admin {user.get('_id')} cleared demand cache: {cleared} entries")
    
    return success_response(
        "Demand cache cleared",
        {"entries_cleared": cleared, "cache_stats": get_cache_stats()},
    )


@router.get("/demand-forecast")
def get_demand_forecast(
    hours: int = 24,
    user=Depends(require_roles("admin")),
):
    """
    Get demand forecast for the next N hours.
    """
    from ml.demand_predictor import predict_demand_range
    from datetime import datetime
    
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")
    
    start_time = datetime.utcnow()
    predictions = predict_demand_range(start_time=start_time, hours=hours)
    
    return success_response(
        f"Demand forecast for next {hours} hours",
        {"predictions": predictions},
    )


# ============================================================================
# Fraud Detection Endpoints
# ============================================================================

class FraudTrainRequest(BaseModel):
    """Request model for training the fraud detection model."""
    contamination: float = Field(default=0.1, ge=0.01, le=0.5, description="Expected anomaly proportion")
    min_samples: int = Field(default=50, ge=10, description="Minimum training samples")
    use_synthetic_if_needed: bool = Field(default=True)


@router.get("/fraud-score/{entity_type}/{entity_id}")
def get_fraud_score_endpoint(
    entity_type: str,
    entity_id: str,
    store_result: bool = False,
    user=Depends(require_roles("admin")),
):
    """
    Get fraud/anomaly score for an entity.
    
    Args:
        entity_type: "technician" or "service"
        entity_id: ID of the entity
        store_result: Whether to store the result in fraud_flags collection
    
    Returns:
        - anomaly_score: Negative = more anomalous
        - is_anomaly: Whether entity is flagged
        - confidence: Confidence level (0-1)
        - top_contributing_features: Most suspicious features
    
    Includes timeout protection (5s) to ensure system stability.
    """
    from ml.fraud_predictor import predict_fraud_score, store_fraud_flag, _fallback_prediction
    
    if entity_type not in ["technician", "service"]:
        raise HTTPException(
            status_code=400,
            detail="entity_type must be 'technician' or 'service'"
        )
    
    start_time = time.perf_counter()
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(predict_fraud_score, entity_id, entity_type)
            try:
                result = future.result(timeout=PREDICTION_TIMEOUT)
            except FuturesTimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Fraud prediction timed out after {PREDICTION_TIMEOUT}s, using fallback"
                )
                
                # Return default non-anomaly result
                result = {
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "anomaly_score": 0.0,
                    "is_anomaly": False,
                    "confidence": 0.0,
                    "threshold": -0.3,
                    "prediction_source": "fallback_timeout",
                    "model_available": False,
                    "latency_ms": round(latency_ms, 3),
                    "timed_out": True,
                }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Fraud prediction error: {e}")
        
        result = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "anomaly_score": 0.0,
            "is_anomaly": False,
            "confidence": 0.0,
            "prediction_source": "fallback_error",
            "model_available": False,
            "latency_ms": round(latency_ms, 3),
            "error": str(e),
        }
    
    if result.get("error") and "not found" in result["error"].lower():
        raise HTTPException(status_code=404, detail=result["error"])
    
    if store_result and not result.get("timed_out"):
        try:
            store_fraud_flag(entity_id, entity_type, result)
        except Exception as e:
            logger.warning(f"Failed to store fraud flag: {e}")
    
    logger.info(
        f"Fraud score: {entity_type}/{entity_id}, "
        f"score={result.get('anomaly_score', 0):.3f}, anomaly={result.get('is_anomaly', False)}, "
        f"source={result.get('prediction_source', 'unknown')}"
    )
    
    return success_response("Fraud score", result)


@router.get("/fraud-model-status")
def get_fraud_model_status(user=Depends(require_roles("admin"))):
    """
    Get the current status of the fraud detection model.
    """
    from ml.fraud_predictor import get_fraud_model_info
    
    info = get_fraud_model_info()
    return success_response("Fraud model status", info)


@router.post("/train-fraud")
def train_fraud_model_endpoint(
    payload: Optional[FraudTrainRequest] = None,
    user=Depends(require_roles("admin")),
):
    """
    Train the fraud detection (Isolation Forest) model.
    
    Uses historical data or synthetic data if insufficient history.
    """
    from ml.fraud_detection import train_fraud_model
    
    contamination = 0.1
    min_samples = 50
    use_synthetic = True
    
    if payload:
        contamination = payload.contamination
        min_samples = payload.min_samples
        use_synthetic = payload.use_synthetic_if_needed
    
    logger.info(f"Admin {user.get('_id')} initiated fraud model training")
    
    result = train_fraud_model(
        contamination=contamination,
        min_samples=min_samples,
        use_synthetic_if_needed=use_synthetic,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Fraud model training failed"),
        )
    
    logger.info(f"Fraud model training completed: {result.get('anomalies_detected')} anomalies")
    return success_response("Fraud model trained successfully", result)


@router.post("/reload-fraud-model")
def reload_fraud_model_endpoint(user=Depends(require_roles("admin"))):
    """
    Reload the fraud model from disk.
    """
    from ml.fraud_predictor import load_fraud_model, get_fraud_model_info
    
    success, error = load_fraud_model()
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to reload fraud model: {error}")
    
    logger.info(f"Admin {user.get('_id')} reloaded the fraud model")
    return success_response("Fraud model reloaded", get_fraud_model_info())


@router.post("/train-fraud-and-reload")
def train_fraud_and_reload_endpoint(
    payload: Optional[FraudTrainRequest] = None,
    user=Depends(require_roles("admin")),
):
    """
    Train a new fraud model and immediately reload it.
    """
    from ml.fraud_detection import train_fraud_model
    from ml.fraud_predictor import load_fraud_model, get_fraud_model_info
    
    contamination = 0.1
    min_samples = 50
    use_synthetic = True
    
    if payload:
        contamination = payload.contamination
        min_samples = payload.min_samples
        use_synthetic = payload.use_synthetic_if_needed
    
    logger.info(f"Admin {user.get('_id')} initiated fraud train-and-reload")
    
    # Train
    train_result = train_fraud_model(
        contamination=contamination,
        min_samples=min_samples,
        use_synthetic_if_needed=use_synthetic,
    )
    
    if not train_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=train_result.get("error", "Training failed"),
        )
    
    # Reload
    success, error = load_fraud_model()
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Training succeeded but reload failed: {error}",
        )
    
    return success_response(
        "Fraud model trained and reloaded",
        {
            "training": train_result,
            "model_info": get_fraud_model_info(),
        },
    )


@router.post("/fraud-scan")
def fraud_scan_endpoint(user=Depends(require_roles("admin"))):
    """
    Scan all technicians and completed services for fraud.
    
    Flags entities with anomaly scores below threshold.
    Results are stored in fraud_flags collection.
    Includes timeout protection (60s) to ensure system stability.
    """
    from ml.fraud_predictor import scan_all_entities
    from datetime import datetime
    
    logger.info(f"Admin {user.get('_id')} initiated fraud scan")
    
    start_time = time.perf_counter()
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scan_all_entities)
            try:
                results = future.result(timeout=SCAN_TIMEOUT)
            except FuturesTimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"Fraud scan timed out after {SCAN_TIMEOUT}s"
                )
                
                results = {
                    "technicians_scanned": 0,
                    "technicians_flagged": 0,
                    "services_scanned": 0,
                    "services_flagged": 0,
                    "newly_flagged": [],
                    "scanned_at": datetime.utcnow().isoformat(),
                    "timed_out": True,
                    "latency_ms": round(latency_ms, 3),
                    "error": f"Scan timed out after {SCAN_TIMEOUT}s",
                }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Fraud scan error: {e}")
        
        results = {
            "technicians_scanned": 0,
            "technicians_flagged": 0,
            "services_scanned": 0,
            "services_flagged": 0,
            "newly_flagged": [],
            "scanned_at": datetime.utcnow().isoformat(),
            "error": str(e),
            "latency_ms": round(latency_ms, 3),
        }
    
    logger.info(
        f"Fraud scan completed: "
        f"{results.get('technicians_flagged', 0)}/{results.get('technicians_scanned', 0)} technicians, "
        f"{results.get('services_flagged', 0)}/{results.get('services_scanned', 0)} services flagged"
    )
    
    return success_response("Fraud scan completed", results)


@router.get("/fraud-flags")
def get_fraud_flags(
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    user=Depends(require_roles("admin")),
):
    """
    Get all fraud flags from the database.
    
    Args:
        status: Filter by status ("pending_review", "cleared", "confirmed")
        entity_type: Filter by entity type ("technician", "service")
    """
    from database import fraud_flags_collection
    
    query = {}
    if status:
        query["status"] = status
    if entity_type:
        query["entity_type"] = entity_type
    
    flags = []
    for flag in fraud_flags_collection.find(query).sort("flagged_at", -1):
        flag["_id"] = str(flag.get("_id"))
        flags.append(flag)
    
    return success_response("Fraud flags", {"count": len(flags), "flags": flags})


@router.patch("/fraud-flags/{entity_id}/status")
def update_fraud_flag_status(
    entity_id: str,
    status: str,
    user=Depends(require_roles("admin")),
):
    """
    Update the status of a fraud flag.
    
    Args:
        entity_id: ID of the flagged entity
        status: New status ("pending_review", "cleared", "confirmed", "false_positive")
    """
    from database import fraud_flags_collection
    
    valid_statuses = ["pending_review", "cleared", "confirmed", "false_positive"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    result = fraud_flags_collection.update_one(
        {"entity_id": entity_id},
        {
            "$set": {
                "status": status,
                "reviewed_by": user.get("_id"),
                "reviewed_at": datetime.utcnow(),
            }
        },
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fraud flag not found")
    
    logger.info(f"Fraud flag status updated: {entity_id} -> {status} by {user.get('_id')}")
    return success_response("Fraud flag status updated", {"entity_id": entity_id, "status": status})


# ============================================================================
# Model Registry Endpoints - Model Versioning & Metrics
# ============================================================================


@router.get("/models")
def get_all_models_status(user=Depends(require_roles("admin"))):
    """
    Get status overview of all registered ML models.
    
    Returns active versions, accuracy metrics, and deployment timestamps.
    """
    from ml.model_registry import model_registry
    
    status = model_registry.get_all_models_status()
    return success_response("ML models status", status)


@router.get("/models/{model_name}/history")
def get_model_history(
    model_name: str,
    limit: int = 10,
    user=Depends(require_roles("admin")),
):
    """
    Get training history for a specific model.
    
    Shows all versions with their metrics and training details.
    """
    from ml.model_registry import model_registry
    
    history = model_registry.get_model_history(model_name, limit)
    return success_response(
        f"Model history: {model_name}",
        {"model_name": model_name, "versions": history}
    )


@router.get("/models/{model_name}/active")
def get_active_model(
    model_name: str,
    user=Depends(require_roles("admin")),
):
    """
    Get the currently deployed/active model version.
    """
    from ml.model_registry import model_registry
    
    model = model_registry.get_active_model(model_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"No active model found for {model_name}")
    
    return success_response(f"Active model: {model_name}", model)


@router.post("/models/{model_name}/deploy")
def deploy_model_version(
    model_name: str,
    version: Optional[str] = None,
    user=Depends(require_roles("admin")),
):
    """
    Deploy a specific model version as the active version.
    
    If version is not specified, deploys the latest version.
    """
    from ml.model_registry import model_registry
    
    try:
        model = model_registry.deploy_model(model_name, version)
        logger.log_admin_action(
            user.get("_id"),
            "deploy_model",
            f"model={model_name}, version={model['version']}"
        )
        return success_response(f"Model deployed: {model_name}", model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Import datetime for the endpoint
from datetime import datetime
