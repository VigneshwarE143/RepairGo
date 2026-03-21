from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from database import (
    categories_collection,
    services_collection,
    technicians_collection,
    users_collection,
    fraud_flags_collection,
)
from utils.auth_utils import require_roles
from utils.fraud_utils import (
    flag_service_if_price_deviation,
    flag_technician_if_needed,
    TECH_CANCEL_THRESHOLD,
)
from utils.reassignment_utils import reassign_stale_jobs
from utils.response_utils import success_response
from utils.logger import logger
from utils.background_job_monitor import job_monitor

router = APIRouter()


@router.get("/admin/users")
def admin_list_users(user=Depends(require_roles("admin"))):
    users = []
    for item in users_collection.find({"is_active": True}, {"password": 0}):
        item["_id"] = str(item.get("_id"))
        users.append(item)
    logger.log_admin_action(user.get("_id"), "list_users", f"count={len(users)}")
    return success_response("Users retrieved", users)


@router.get("/admin/technicians")
def admin_list_technicians(user=Depends(require_roles("admin"))):
    technicians = []
    for item in technicians_collection.find({"is_active": True}):
        item["_id"] = str(item.get("_id"))
        completed = int(item.get("completed_jobs", 0) or 0)
        rating = float(item.get("rating", 0.0) or 0.0)
        cancelled = int(item.get("cancelled_jobs", 0) or 0)
        total_jobs = max(completed + cancelled, 1)
        cancellation_rate = cancelled / total_jobs
        performance_score = (completed * 0.4) + (rating * 0.4) - (cancellation_rate * 0.2)
        item["performance_score"] = performance_score
        item["cancellation_rate"] = cancellation_rate
        item["is_flagged"] = fraud_flags_collection.find_one(
            {"entity_id": str(item.get("_id"))}
        ) is not None
        technicians.append(item)
    logger.log_admin_action(
        user.get("_id"), "list_technicians", f"count={len(technicians)}"
    )
    return success_response("Technicians retrieved", technicians)


@router.get("/admin/requests")
def admin_list_requests(user=Depends(require_roles("admin"))):
    requests = []
    for item in services_collection.find({"is_active": True}):
        item["_id"] = str(item.get("_id"))
        item["is_flagged"] = fraud_flags_collection.find_one(
            {"entity_id": str(item.get("_id"))}
        ) is not None
        requests.append(item)
    logger.log_admin_action(user.get("_id"), "list_requests", f"count={len(requests)}")
    return success_response("Requests retrieved", requests)


@router.get("/admin/revenue")
def admin_revenue_stats(user=Depends(require_roles("admin"))):
    pipeline = [
        {"$match": {"status": {"$in": ["completed", "rated"]}, "is_active": True}},
        {"$group": {"_id": None, "total": {"$sum": "$final_price"}}},
    ]
    result = list(services_collection.aggregate(pipeline))
    total = result[0]["total"] if result else 0.0

    by_category = list(
        services_collection.aggregate(
            [
                {"$match": {"status": {"$in": ["completed", "rated"]}, "is_active": True}},
                {
                    "$group": {
                        "_id": "$category",
                        "revenue": {"$sum": "$final_price"},
                        "count": {"$sum": 1},
                    }
                },
            ]
        )
    )

    by_month = list(
        services_collection.aggregate(
            [
                {"$match": {"status": {"$in": ["completed", "rated"]}, "is_active": True}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m", "date": "$created_at"}
                        },
                        "revenue": {"$sum": "$final_price"},
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": -1}},
            ]
        )
    )

    logger.log_admin_action(
        user.get("_id"), "revenue_stats", f"total={total}"
    )
    return success_response(
        "Revenue statistics",
        {
            "total_revenue": total,
            "by_category": by_category,
            "by_month": by_month,
        },
    )


@router.get("/admin/categories")
def admin_list_categories(user=Depends(require_roles("admin"))):
    """List all service categories."""
    categories = []
    for item in categories_collection.find({}):
        item["_id"] = str(item.get("_id"))
        categories.append(item)
    logger.log_admin_action(user.get("_id"), "list_categories", f"count={len(categories)}")
    return success_response("Categories retrieved", categories)


@router.post("/admin/categories")
def admin_upsert_category(
    payload: dict,
    user=Depends(require_roles("admin")),
):
    name = payload.get("name")
    base_price = payload.get("base_price")
    travel_rate = payload.get("travel_rate", 2.0)
    urgency_addon = payload.get("urgency_addon", {"low": 0, "medium": 10, "high": 25})

    if not name or not isinstance(base_price, (int, float)):
        raise HTTPException(status_code=400, detail="Invalid category payload")

    categories_collection.update_one(
        {"name": name},
        {
            "$set": {
                "name": name,
                "base_price": float(base_price),
                "travel_rate": float(travel_rate),
                "urgency_addon": urgency_addon,
            }
        },
        upsert=True,
    )

    logger.log_admin_action(
        user.get("_id"), "upsert_category", f"name={name}, price={base_price}"
    )
    return success_response("Category saved")


@router.delete("/admin/categories/{category_id}")
def admin_delete_category(
    category_id: str,
    user=Depends(require_roles("admin")),
):
    """Delete a service category by ID."""
    try:
        object_id = ObjectId(category_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid category id")

    result = categories_collection.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")

    logger.log_admin_action(user.get("_id"), "delete_category", f"id={category_id}")
    return success_response("Category deleted")


@router.post("/admin/reassign-stale")
def admin_reassign_stale(user=Depends(require_roles("admin"))):
    reassigned, attempted = reassign_stale_jobs(stale_minutes=5)
    logger.log_admin_action(
        user.get("_id"),
        "reassign_stale",
        f"reassigned={reassigned}, attempted={attempted}",
    )
    return success_response(
        "Stale jobs reassigned",
        {"reassigned": reassigned, "attempted": attempted},
    )


@router.post("/admin/fraud/check")
def admin_fraud_check(user=Depends(require_roles("admin"))):
    """
    Run ML-based fraud detection scan on all entities.
    
    Uses Isolation Forest anomaly detection if model is available,
    otherwise falls back to rule-based detection.
    """
    try:
        from ml.fraud_predictor import scan_all_entities, is_fraud_model_available
        
        if is_fraud_model_available():
            # Use ML-based fraud detection
            results = scan_all_entities()
            
            logger.log_admin_action(
                user.get("_id"),
                "fraud_check_ml",
                f"tech_flags={results['technicians_flagged']}, request_flags={results['services_flagged']}",
            )
            
            return success_response(
                "ML-based fraud check completed",
                {
                    "method": "isolation_forest",
                    "technicians_scanned": results["technicians_scanned"],
                    "technicians_flagged": results["technicians_flagged"],
                    "services_scanned": results["services_scanned"],
                    "services_flagged": results["services_flagged"],
                    "newly_flagged": results["newly_flagged"][:10],  # Top 10
                },
            )
    except ImportError:
        pass  # Fall back to rule-based
    
    # Fallback to rule-based detection
    tech_flags = 0
    request_flags = 0

    for tech in technicians_collection.find({"is_active": True}):
        if flag_technician_if_needed(tech):
            fraud_flags_collection.update_one(
                {"entity_id": str(tech.get("_id"))},
                {
                    "$set": {
                        "entity_id": str(tech.get("_id")),
                        "entity_type": "technician",
                        "reason": "cancellation_threshold",
                        "threshold": TECH_CANCEL_THRESHOLD,
                        "actual_value": tech.get("cancelled_jobs", 0),
                        "flagged_at": datetime.utcnow(),
                        "status": "pending_review",
                        "prediction_source": "rule_based",
                    }
                },
                upsert=True,
            )
            tech_flags += 1
            logger.log_fraud_flag("technician", str(tech.get("_id")), "cancellation_threshold")

    for service in services_collection.find({"is_active": True}):
        if flag_service_if_price_deviation(service):
            fraud_flags_collection.update_one(
                {"entity_id": str(service.get("_id"))},
                {
                    "$set": {
                        "entity_id": str(service.get("_id")),
                        "entity_type": "service",
                        "reason": "price_deviation",
                        "estimated": service.get("estimated_price"),
                        "final": service.get("final_price"),
                        "flagged_at": datetime.utcnow(),
                        "status": "pending_review",
                        "prediction_source": "rule_based",
                    }
                },
                upsert=True,
            )
            request_flags += 1
            logger.log_fraud_flag("service", str(service.get("_id")), "price_deviation")

    logger.log_admin_action(
        user.get("_id"),
        "fraud_check_rules",
        f"tech_flags={tech_flags}, request_flags={request_flags}",
    )
    return success_response(
        "Rule-based fraud check completed",
        {
            "method": "rule_based",
            "technicians_flagged": tech_flags,
            "requests_flagged": request_flags,
        },
    )


@router.get("/admin/health/background-jobs")
def background_job_health(user=Depends(require_roles("admin"))):
    """Monitor the health and status of background jobs."""
    status = job_monitor.get_status()
    logger.log_admin_action(user.get("_id"), "check_job_health", f"status={status['status']}")
    return success_response("Background job status", status)


# ============================================================================
# Soft Delete / Deactivation Endpoints
# ============================================================================


@router.patch("/admin/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    user=Depends(require_roles("admin")),
):
    """
    Soft delete a user by setting is_active=False.
    
    The user will be hidden from queries but data is preserved.
    """
    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    
    result = users_collection.update_one(
        {"_id": object_id, "is_active": True},
        {
            "$set": {
                "is_active": False,
                "deactivated_at": datetime.utcnow(),
                "deactivated_by": user.get("_id"),
            }
        },
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found or already deactivated")
    
    logger.log_admin_action(user.get("_id"), "deactivate_user", f"user_id={user_id}")
    return success_response("User deactivated", {"user_id": user_id})


@router.patch("/admin/users/{user_id}/reactivate")
def reactivate_user(
    user_id: str,
    user=Depends(require_roles("admin")),
):
    """
    Reactivate a previously deactivated user.
    """
    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    
    result = users_collection.update_one(
        {"_id": object_id, "is_active": False},
        {
            "$set": {
                "is_active": True,
                "reactivated_at": datetime.utcnow(),
                "reactivated_by": user.get("_id"),
            },
            "$unset": {
                "deactivated_at": "",
                "deactivated_by": "",
            }
        },
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found or already active")
    
    logger.log_admin_action(user.get("_id"), "reactivate_user", f"user_id={user_id}")
    return success_response("User reactivated", {"user_id": user_id})


@router.patch("/admin/technicians/{technician_id}/deactivate")
def deactivate_technician(
    technician_id: str,
    user=Depends(require_roles("admin")),
):
    """
    Soft delete a technician by setting is_active=False.
    
    Active jobs will remain assigned but no new assignments will be made.
    """
    try:
        object_id = ObjectId(technician_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid technician id")
    
    # Check for active assignments
    active_jobs = services_collection.count_documents({
        "technician_id": technician_id,
        "status": {"$in": ["assigned", "on_the_way", "in_progress"]},
        "is_active": True,
    })
    
    result = technicians_collection.update_one(
        {"_id": object_id, "is_active": True},
        {
            "$set": {
                "is_active": False,
                "availability": False,
                "deactivated_at": datetime.utcnow(),
                "deactivated_by": user.get("_id"),
            }
        },
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Technician not found or already deactivated")
    
    logger.log_admin_action(
        user.get("_id"),
        "deactivate_technician",
        f"technician_id={technician_id}, active_jobs={active_jobs}"
    )
    return success_response(
        "Technician deactivated",
        {
            "technician_id": technician_id,
            "active_jobs_remaining": active_jobs,
            "warning": "Technician has active jobs" if active_jobs > 0 else None,
        }
    )


@router.patch("/admin/technicians/{technician_id}/reactivate")
def reactivate_technician(
    technician_id: str,
    user=Depends(require_roles("admin")),
):
    """
    Reactivate a previously deactivated technician.
    """
    try:
        object_id = ObjectId(technician_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid technician id")
    
    result = technicians_collection.update_one(
        {"_id": object_id, "is_active": False},
        {
            "$set": {
                "is_active": True,
                "reactivated_at": datetime.utcnow(),
                "reactivated_by": user.get("_id"),
            },
            "$unset": {
                "deactivated_at": "",
                "deactivated_by": "",
            }
        },
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Technician not found or already active")
    
    logger.log_admin_action(user.get("_id"), "reactivate_technician", f"technician_id={technician_id}")
    return success_response("Technician reactivated", {"technician_id": technician_id})


@router.get("/admin/deactivated/users")
def list_deactivated_users(user=Depends(require_roles("admin"))):
    """List all deactivated (soft-deleted) users."""
    users = []
    for item in users_collection.find({"is_active": False}, {"password": 0}):
        item["_id"] = str(item.get("_id"))
        users.append(item)
    return success_response("Deactivated users", users)


@router.get("/admin/deactivated/technicians")
def list_deactivated_technicians(user=Depends(require_roles("admin"))):
    """List all deactivated (soft-deleted) technicians."""
    technicians = []
    for item in technicians_collection.find({"is_active": False}):
        item["_id"] = str(item.get("_id"))
        technicians.append(item)
    return success_response("Deactivated technicians", technicians)


# ============================================================================
# Cache Management Endpoints
# ============================================================================


@router.get("/admin/cache/stats")
def get_cache_stats(user=Depends(require_roles("admin"))):
    """Get cache statistics for technician selection."""
    from utils.technician_selection import get_cache_stats
    
    stats = get_cache_stats()
    return success_response("Cache statistics", stats)


@router.post("/admin/cache/clear")
def clear_cache(user=Depends(require_roles("admin"))):
    """Clear the technician selection cache."""
    from utils.technician_selection import clear_selection_cache, get_cache_stats
    
    clear_selection_cache()
    logger.log_admin_action(user.get("_id"), "clear_cache", "selection_cache")
    return success_response("Cache cleared", get_cache_stats())

