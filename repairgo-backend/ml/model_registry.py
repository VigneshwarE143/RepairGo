"""
ML Model Registry for tracking model versions, training metrics, and deployment history.

Provides production-grade model versioning and performance tracking.
"""

from datetime import datetime
from typing import Dict, Optional, List, Any
import hashlib
import json

from database import ml_models_collection
from utils.logger import logger


class ModelRegistry:
    """
    Registry for tracking ML model versions, training metrics, and performance.
    
    Stores:
    - Model metadata (name, version, type)
    - Training metrics (accuracy, validation scores)
    - Feature information
    - Training timestamps
    - Deployment status
    """
    
    @staticmethod
    def register_model(
        model_name: str,
        model_type: str,
        version: str = None,
        accuracy: float = None,
        validation_score: float = None,
        feature_count: int = None,
        feature_names: List[str] = None,
        training_samples: int = None,
        hyperparameters: Dict[str, Any] = None,
        training_duration_seconds: float = None,
        notes: str = None,
    ) -> Dict:
        """
        Register a newly trained model with its metrics.
        
        Args:
            model_name: Unique identifier (e.g., 'reliability_rf', 'demand_rf', 'fraud_if')
            model_type: Algorithm type (e.g., 'RandomForestClassifier', 'IsolationForest')
            version: Semantic version (auto-incremented if None)
            accuracy: Training accuracy (0-1)
            validation_score: Cross-validation score (0-1)
            feature_count: Number of input features
            feature_names: List of feature names
            training_samples: Number of training samples
            hyperparameters: Model hyperparameters
            training_duration_seconds: How long training took
            notes: Additional notes
        
        Returns:
            The registered model document
        """
        # Auto-generate version if not provided
        if version is None:
            latest = ml_models_collection.find_one(
                {"model_name": model_name},
                sort=[("version_number", -1)]
            )
            if latest:
                version_number = latest.get("version_number", 0) + 1
            else:
                version_number = 1
            version = f"1.0.{version_number}"
        else:
            # Parse version number from string
            try:
                version_number = int(version.split(".")[-1])
            except (ValueError, IndexError):
                version_number = 1
        
        # Generate content hash for model fingerprinting
        content_hash = hashlib.md5(
            json.dumps({
                "model_name": model_name,
                "version": version,
                "trained_at": datetime.utcnow().isoformat(),
            }, sort_keys=True).encode()
        ).hexdigest()[:12]
        
        model_doc = {
            "model_name": model_name,
            "model_type": model_type,
            "version": version,
            "version_number": version_number,
            "content_hash": content_hash,
            "accuracy": accuracy,
            "validation_score": validation_score,
            "feature_count": feature_count,
            "feature_names": feature_names or [],
            "training_samples": training_samples,
            "hyperparameters": hyperparameters or {},
            "training_duration_seconds": training_duration_seconds,
            "notes": notes,
            "trained_at": datetime.utcnow(),
            "deployed_at": None,
            "is_active": False,  # Not deployed yet
            "created_at": datetime.utcnow(),
        }
        
        result = ml_models_collection.insert_one(model_doc)
        model_doc["_id"] = str(result.inserted_id)
        
        logger.info(
            f"Model registered: {model_name} v{version} "
            f"(accuracy={accuracy}, validation={validation_score})"
        )
        
        return model_doc
    
    @staticmethod
    def deploy_model(model_name: str, version: str = None) -> Dict:
        """
        Mark a model version as the active/deployed version.
        
        Args:
            model_name: Model identifier
            version: Version to deploy (latest if None)
        
        Returns:
            The deployed model document
        """
        # Deactivate all previous versions
        ml_models_collection.update_many(
            {"model_name": model_name, "is_active": True},
            {"$set": {"is_active": False}}
        )
        
        # Find the version to deploy
        if version:
            model = ml_models_collection.find_one(
                {"model_name": model_name, "version": version}
            )
        else:
            # Deploy latest version
            model = ml_models_collection.find_one(
                {"model_name": model_name},
                sort=[("version_number", -1)]
            )
        
        if not model:
            raise ValueError(f"Model {model_name} version {version} not found")
        
        # Activate this version
        ml_models_collection.update_one(
            {"_id": model["_id"]},
            {"$set": {"is_active": True, "deployed_at": datetime.utcnow()}}
        )
        
        logger.info(f"Model deployed: {model_name} v{model['version']}")
        
        model["is_active"] = True
        model["_id"] = str(model["_id"])
        return model
    
    @staticmethod
    def get_active_model(model_name: str) -> Optional[Dict]:
        """Get the currently deployed/active model version."""
        model = ml_models_collection.find_one(
            {"model_name": model_name, "is_active": True}
        )
        if model:
            model["_id"] = str(model["_id"])
        return model
    
    @staticmethod
    def get_model_history(
        model_name: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Get training history for a model."""
        models = list(ml_models_collection.find(
            {"model_name": model_name},
            sort=[("version_number", -1)],
            limit=limit,
        ))
        for m in models:
            m["_id"] = str(m["_id"])
        return models
    
    @staticmethod
    def get_all_models_status() -> Dict[str, Dict]:
        """Get status of all registered models."""
        model_names = ml_models_collection.distinct("model_name")
        status = {}
        
        for name in model_names:
            active = ml_models_collection.find_one(
                {"model_name": name, "is_active": True}
            )
            total_versions = ml_models_collection.count_documents(
                {"model_name": name}
            )
            
            status[name] = {
                "total_versions": total_versions,
                "active_version": active["version"] if active else None,
                "active_accuracy": active.get("accuracy") if active else None,
                "deployed_at": active.get("deployed_at").isoformat() if active and active.get("deployed_at") else None,
            }
        
        return status
    
    @staticmethod
    def log_prediction_metrics(
        model_name: str,
        predictions_count: int,
        avg_latency_ms: float,
        fallback_rate: float,
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        """
        Log prediction performance metrics for monitoring.
        
        This can be used for tracking model performance in production.
        """
        metrics_doc = {
            "model_name": model_name,
            "metric_type": "prediction_performance",
            "predictions_count": predictions_count,
            "avg_latency_ms": avg_latency_ms,
            "fallback_rate": fallback_rate,
            "period_start": period_start,
            "period_end": period_end,
            "created_at": datetime.utcnow(),
        }
        ml_models_collection.insert_one(metrics_doc)


# Singleton instance
model_registry = ModelRegistry()
