from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from database import services_collection, technicians_collection, categories_collection, payments_collection
from models.service_model import (
    ServiceCreate,
    ServiceEstimate,
    ServiceRating,
    ServiceStatusUpdate,
    PaymentRequest,
    RefundRequest,
    ServiceCancelRequest,
    JobAcceptReject,
    ChooseTechnician,
    TechnicianResponse,
)
from utils.auth_utils import require_roles
from utils.technician_selection import (
    calculate_score,
    haversine_distance_km,
    estimate_eta_minutes,
    select_best_technician,
    resolve_technician_coordinates,
)
from utils.pricing import estimate_distance_km, estimate_price
from utils.notification_utils import create_notification, EventType
from utils.response_utils import success_response
from utils.logger import logger

router = APIRouter()

VALID_CATEGORIES = set()
ACTIVE_JOB_STATUSES = {"assigned", "accepted", "on_the_way", "in_progress", "awaiting_technician_acceptance"}

# Cancellation reasons for UI display
CANCELLATION_REASONS = {
    "changed_mind": "Changed my mind",
    "found_another_service": "Found another service provider",
    "technician_too_far": "Technician is too far away",
    "price_too_high": "Price is too high",
    "emergency_resolved": "Emergency has been resolved",
    "scheduling_conflict": "Scheduling conflict",
    "other": "Other reason",
}



def load_categories():
    global VALID_CATEGORIES
    VALID_CATEGORIES = set(cat["name"] for cat in categories_collection.find({}))


def is_technician_busy(tech_id: str, exclude_service_id: ObjectId | None = None) -> bool:
    """Return True if technician has any active (assigned/accepted/on_the_way/in_progress) job other than exclude_service_id."""
    query = {
        "technician_id": tech_id,
        "status": {"$in": list(ACTIVE_JOB_STATUSES)},
        "is_active": True,
    }
    if exclude_service_id:
        query["_id"] = {"$ne": exclude_service_id}
    return services_collection.count_documents(query) > 0


@router.post("/services")
def create_service_request(
    payload: ServiceCreate,
    user=Depends(require_roles("customer")),
):
    load_categories()
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Allowed: {VALID_CATEGORIES}",
        )
    
    data = payload.dict()
    data["status"] = "pending"
    data["customer_id"] = user.get("_id")
    data["created_at"] = datetime.utcnow()
    data["is_active"] = True
    result = services_collection.insert_one(data)
    service_id = result.inserted_id
    logger.info(f"Service created: service_id={service_id}, category={payload.category}")
    
    # Find best technicians - return Top 3 suggestions for customer to choose
    response_data = {"id": str(service_id)}
    try:
        # Find available technicians with matching skills
        technicians = list(
            technicians_collection.find({
                "availability": True, 
                "is_active": True,
                "skills": payload.category  # Must have the required skill
            })
        )

        # Exclude technicians who already have an active job
        technicians = [
            t for t in technicians if not is_technician_busy(str(t.get("_id")))
        ]
        
        if technicians:
            # Get the service document for scoring
            service = services_collection.find_one({"_id": service_id})
            
            # Score ALL available technicians
            scored_list = []
            for tech in technicians:
                score, components = calculate_score(service, tech)
                if score > 0.3:  # Minimum score threshold
                    tech_lat, tech_lon, _ = resolve_technician_coordinates(tech)
                    service_location = service.get("location", {})
                    distance_km = haversine_distance_km(
                        service_location.get("latitude", 0.0),
                        service_location.get("longitude", 0.0),
                        tech_lat,
                        tech_lon,
                    )
                    eta_minutes = estimate_eta_minutes(distance_km)
                    scored_list.append({
                        "technician_id": str(tech.get("_id")),
                        "score": round(score, 4),
                        "name": tech.get("name"),
                        "rating": tech.get("rating", 0),
                        "completed_jobs": tech.get("completed_jobs", 0),
                        "phone": tech.get("phone"),
                        "eta_minutes": round(eta_minutes, 0),
                        "distance_km": round(distance_km, 2),
                        "ml_score": round(score * 100, 1),
                        "skills": tech.get("skills", []),
                        "prediction_source": components.get("prediction_source", "model"),
                    })
            
            # Sort by score descending and take top 3
            scored_list.sort(key=lambda x: x["score"], reverse=True)
            top_3 = scored_list[:3]
            
            if top_3:
                # Store suggested technicians in the service record
                suggested_for_db = [
                    {"technician_id": t["technician_id"], "score": t["score"]}
                    for t in top_3
                ]
                services_collection.update_one(
                    {"_id": service_id},
                    {
                        "$set": {
                            "suggested_technicians": suggested_for_db,
                            "technician_response": "pending",
                        }
                    },
                )
                
                response_data["has_recommendation"] = True
                response_data["suggested_technicians"] = top_3
                logger.info(f"Suggested {len(top_3)} technicians for service {service_id}")
            else:
                logger.info(f"No suitable technician found for service {service_id}")
                response_data["has_recommendation"] = False
                response_data["suggested_technicians"] = []
        else:
            logger.info(f"No available technicians for category {payload.category}")
            response_data["has_recommendation"] = False
            response_data["suggested_technicians"] = []
    except Exception as e:
        logger.error(f"Auto-selection failed: {e}")
        response_data["has_recommendation"] = False
        response_data["suggested_technicians"] = []
    
    return success_response("Service request created", response_data)


@router.post("/services/estimate")
def estimate_service_price(
    payload: ServiceEstimate,
    user=Depends(require_roles("customer")),
):
    load_categories()
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Allowed: {VALID_CATEGORIES}",
        )
    
    technicians = list(
        technicians_collection.find({"availability": True, "is_active": True})
    )

    technicians = [
        t for t in technicians if not is_technician_busy(str(t.get("_id")))
    ]
    distance_km = estimate_distance_km(payload.location.dict(), technicians)
    active_requests = services_collection.count_documents(
        {
            "status": {
                "$in": ["pending", "assigned", "on_the_way", "in_progress"],
            },
            "is_active": True,
        }
    )
    pricing = estimate_price(
        category=payload.category,
        urgency=payload.urgency,
        distance_km=distance_km,
        active_requests=active_requests,
    )
    return success_response("Price estimate", {"estimate": pricing})


@router.post("/services/{service_id}/choose-technician")
def choose_technician(
    service_id: str,
    payload: ChooseTechnician,
    user=Depends(require_roles("customer")),
):
    """
    Customer chooses a technician from the suggested list.
    Sets status to awaiting_technician_acceptance and notifies the technician.
    """
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
        "customer_id": user.get("_id"),
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("status") != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Service is '{service.get('status')}'. Can only choose technician when pending."
        )
    
    # Verify technician is in the suggested list OR is a valid available technician
    suggested = service.get("suggested_technicians", [])
    suggested_ids = [s["technician_id"] for s in suggested]
    
    is_in_suggested = payload.technician_id in suggested_ids
    
    # Verify technician still exists and is available
    try:
        tech_object_id = ObjectId(payload.technician_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid technician id")
    
    tech_query = {
        "_id": tech_object_id,
        "availability": True,
        "is_active": True,
    }
    # If not in stored suggested list, also require matching skills
    if not is_in_suggested:
        tech_query["skills"] = service.get("category")
    
    technician = technicians_collection.find_one(tech_query)
    
    if not technician:
        raise HTTPException(
            status_code=404,
            detail="Selected technician is no longer available or doesn't match this service category"
        )
    
    # Calculate ETA
    service_location = service.get("location", {})
    tech_lat, tech_lon, _ = resolve_technician_coordinates(technician)
    distance_km = haversine_distance_km(
        service_location.get("latitude", 0.0),
        service_location.get("longitude", 0.0),
        tech_lat,
        tech_lon,
    )
    eta_minutes = estimate_eta_minutes(distance_km)
    
    # Update service: set requested_technician, change status
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "awaiting_technician_acceptance",
                "requested_technician": payload.technician_id,
                "technician_response": "pending",
                "requested_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "eta_minutes": eta_minutes,
            }
        },
    )
    
    # Notify technician about the job request
    create_notification(
        recipient_id=payload.technician_id,
        event_type=EventType.ASSIGNMENT,
        message=f"New {service.get('category')} job request! Please accept or reject.",
        related_id=str(service_id),
    )
    
    logger.info(f"Customer chose technician: service={service_id}, technician={payload.technician_id}")
    
    return success_response("Technician selected. Awaiting technician acceptance.", {
        "service_id": str(service_id),
        "requested_technician": payload.technician_id,
        "technician_name": technician.get("name"),
        "eta_minutes": round(eta_minutes, 0),
        "distance_km": round(distance_km, 2),
        "status": "awaiting_technician_acceptance",
    })


@router.post("/services/{service_id}/confirm-booking")
def confirm_booking(
    service_id: str,
    user=Depends(require_roles("customer")),
):
    """
    LEGACY: Confirm booking with the recommended technician.
    Now redirects to choose-technician flow. Kept for backward compatibility.
    """
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
        "customer_id": user.get("_id"),
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("status") != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Service already {service.get('status')}. Cannot confirm booking."
        )
    
    # Pick the top suggested technician automatically (legacy behavior)
    suggested = service.get("suggested_technicians", [])
    if not suggested:
        # Fallback: try to find one now
        recommended_tech_id = service.get("recommended_technician_id")
        if not recommended_tech_id:
            category = service.get("category")
            technicians = list(
                technicians_collection.find({
                    "availability": True, 
                    "is_active": True,
                    "skills": category
                })
            )
            technicians = [
                t for t in technicians if not is_technician_busy(str(t.get("_id")), exclude_service_id=object_id)
            ]
            if not technicians:
                raise HTTPException(status_code=404, detail="No available technicians found")
            best, best_score, _ = select_best_technician(service, technicians)
            if not best or best_score < 0.3:
                raise HTTPException(status_code=404, detail="No suitable technician found")
            recommended_tech_id = str(best.get("_id"))
    else:
        recommended_tech_id = suggested[0]["technician_id"]
    
    # Verify technician still available
    try:
        tech_object_id = ObjectId(recommended_tech_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid technician id")
    
    technician = technicians_collection.find_one({
        "_id": tech_object_id,
        "availability": True,
        "is_active": True,
    })
    
    if not technician or is_technician_busy(str(tech_object_id), exclude_service_id=object_id):
        category = service.get("category")
        technicians = list(
            technicians_collection.find({
                "availability": True, 
                "is_active": True,
                "skills": category
            })
        )
        technicians = [
            t for t in technicians if not is_technician_busy(str(t.get("_id")), exclude_service_id=object_id)
        ]
        if not technicians:
            raise HTTPException(status_code=404, detail="No available technicians found")
        best, best_score, _ = select_best_technician(service, technicians)
        if not best or best_score < 0.3:
            raise HTTPException(status_code=404, detail="No suitable technician found")
        technician = best
        recommended_tech_id = str(best.get("_id"))
    
    # Use the new flow: set to awaiting_technician_acceptance
    service_location = service.get("location", {})
    tech_lat, tech_lon, _ = resolve_technician_coordinates(technician)
    distance_km = haversine_distance_km(
        service_location.get("latitude", 0.0),
        service_location.get("longitude", 0.0),
        tech_lat,
        tech_lon,
    )
    eta_minutes = estimate_eta_minutes(distance_km)
    
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "awaiting_technician_acceptance",
                "requested_technician": recommended_tech_id,
                "technician_response": "pending",
                "requested_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "eta_minutes": eta_minutes,
            }
        },
    )
    
    # Notify technician
    create_notification(
        recipient_id=recommended_tech_id,
        event_type=EventType.ASSIGNMENT,
        message=f"New {service.get('category')} job request! Please accept or reject.",
        related_id=str(service_id),
    )
    
    logger.info(f"Booking sent to technician: service={service_id}, technician={recommended_tech_id}")
    
    return success_response("Request sent to technician. Awaiting acceptance.", {
        "service_id": str(service_id),
        "technician_id": recommended_tech_id,
        "technician_name": technician.get("name"),
        "eta_minutes": round(eta_minutes, 0),
        "distance_km": round(distance_km, 2),
        "status": "awaiting_technician_acceptance",
    })


@router.patch("/services/{service_id}/status")
def update_service_status(
    service_id: str,
    payload: ServiceStatusUpdate,
    user=Depends(require_roles("technician")),
):
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Resolve the technician's ID from the technicians collection
    tech_id = user.get("technician_id")
    if not tech_id:
        technician_doc = technicians_collection.find_one({"email": user.get("email")})
        if technician_doc:
            tech_id = str(technician_doc["_id"])

    # Authorize: check both technician_id (assigned) and requested_technician (awaiting)
    assigned_tech = service.get("technician_id")
    requested_tech = service.get("requested_technician")
    if assigned_tech and assigned_tech != tech_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not assigned_tech and requested_tech and requested_tech != tech_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not assigned_tech and not requested_tech:
        raise HTTPException(status_code=403, detail="No technician assigned to this service")

    status_flow = {
        "pending": ["assigned", "awaiting_technician_acceptance"],
        "awaiting_technician_acceptance": ["assigned", "pending"],  # technician accepts → assigned, rejects → pending
        "assigned": ["accepted", "on_the_way"],  # Technician can accept or go directly
        "accepted": ["on_the_way"],
        "on_the_way": ["in_progress"],
        "in_progress": ["completed"],
        "completed": ["rated"],
        "rated": [],
        "cancelled": [],  # Terminal state
    }
    current_status = service.get("status", "pending")
    if payload.status not in status_flow.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {current_status} to {payload.status}",
        )

    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": payload.status,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.STATUS_UPDATE,
            message=f"Job status updated to {payload.status}",
            related_id=str(service.get("_id")),
        )

    logger.info(f"Status updated: service_id={service_id}, new_status={payload.status}")
    return success_response("Status updated")


@router.get("/services/my")
def get_my_services(user=Depends(require_roles("customer"))):
    """Get all service requests for the logged-in customer."""
    customer_id = user.get("_id")
    services = []
    for item in services_collection.find(
        {"customer_id": customer_id, "is_active": True}
    ).sort("updated_at", -1):
        item["_id"] = str(item.get("_id"))
        # Add technician info if assigned
        if item.get("technician_id"):
            tech = technicians_collection.find_one({"_id": ObjectId(item["technician_id"])})
            if tech:
                item["technician_name"] = tech.get("name")
                item["technician_rating"] = tech.get("rating")
                item["technician_location"] = {
                    "latitude": tech.get("latitude"),
                    "longitude": tech.get("longitude"),
                }
        services.append(item)
    return success_response("My services retrieved", services)


@router.get("/services/{service_id}/technician-location")
def get_technician_location(
    service_id: str,
    user=Depends(require_roles("customer", "technician", "admin")),
):
    """Return latest technician location, distance, and ETA for a service."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Authorize
    if user.get("role") == "customer" and service.get("customer_id") != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if user.get("role") == "technician":
        tech_id_from_user = user.get("technician_id")
        if tech_id_from_user and str(tech_id_from_user) != str(service.get("technician_id")):
            raise HTTPException(status_code=403, detail="Forbidden")

    tech_id = service.get("technician_id")
    if not tech_id:
        raise HTTPException(status_code=404, detail="Technician not assigned yet")

    technician = technicians_collection.find_one({"_id": ObjectId(tech_id)})
    if not technician:
        raise HTTPException(status_code=404, detail="Technician profile not found")

    service_location = service.get("location", {}) or {}
    tech_lat, tech_lon, coord_source = resolve_technician_coordinates(technician)
    distance_km = haversine_distance_km(
        service_location.get("latitude", 0.0),
        service_location.get("longitude", 0.0),
        tech_lat,
        tech_lon,
    )
    eta_minutes = estimate_eta_minutes(distance_km)

    return success_response(
        "Technician location",
        {
            "technician_id": str(tech_id),
            "technician_name": technician.get("name"),
            "latitude": tech_lat,
            "longitude": tech_lon,
            "coordinate_source": coord_source,
            "distance_km": round(distance_km, 2),
            "eta_minutes": round(eta_minutes, 0),
            "heading": technician.get("heading"),
            "speed_kmh": technician.get("speed_kmh"),
            "accuracy_meters": technician.get("location_accuracy"),
            "last_location_update": technician.get("last_location_update"),
            "status": service.get("status"),
        },
    )


@router.get("/services/cancellation-reasons")
def get_cancellation_reasons():
    """Get list of cancellation reasons for UI."""
    return success_response("Cancellation reasons", CANCELLATION_REASONS)


@router.post("/services/{service_id}/cancel")
def cancel_service(
    service_id: str,
    payload: ServiceCancelRequest,
    user=Depends(require_roles("customer")),
):
    """Cancel a service request with reason."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("customer_id") != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Can only cancel pending, awaiting_technician_acceptance, assigned, or accepted jobs
    cancellable_statuses = ["pending", "awaiting_technician_acceptance", "assigned", "accepted"]
    if service.get("status") not in cancellable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel service in '{service.get('status')}' status"
        )
    
    # If technician was assigned, decrease their workload
    technician_id = service.get("technician_id")
    if technician_id:
        technicians_collection.update_one(
            {"_id": ObjectId(technician_id)},
            {"$inc": {"workload": -1}}
        )
        # Notify technician
        create_notification(
            recipient_id=technician_id,
            event_type=EventType.CANCELLATION,
            message=f"Job cancelled by customer. Reason: {CANCELLATION_REASONS.get(payload.reason, payload.reason)}",
            related_id=str(service_id),
        )
    
    # Update service status
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": datetime.utcnow(),
                "cancellation_reason": payload.reason,
                "cancellation_notes": payload.additional_notes,
                "updated_at": datetime.utcnow(),
            }
        }
    )
    
    logger.info(f"Service cancelled: service_id={service_id}, reason={payload.reason}")
    return success_response("Service cancelled successfully")


@router.get("/technicians/pending-jobs")
def get_pending_jobs_for_technician(user=Depends(require_roles("technician"))):
    """Get jobs suggested/assigned to technician that need acceptance."""
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    if not tech_id:
        raise HTTPException(status_code=404, detail="Technician not found")
    
    # Find jobs where this technician is the requested_technician awaiting acceptance
    # OR jobs assigned directly to this technician (legacy flow)
    services = list(services_collection.find({
        "$or": [
            {
                "requested_technician": tech_id,
                "status": "awaiting_technician_acceptance",
                "is_active": {"$ne": False},
            },
            {
                "technician_id": tech_id,
                "status": "assigned",
                "is_active": {"$ne": False},
            },
        ]
    }).sort("created_at", -1))
    
    for service in services:
        service["_id"] = str(service["_id"])
        # Add customer location for distance calculation
        if service.get("location"):
            technician = technicians_collection.find_one({"_id": ObjectId(tech_id)})
            if technician:
                tech_lat, tech_lon, _ = resolve_technician_coordinates(technician)
                distance = haversine_distance_km(
                    service["location"].get("latitude", 0),
                    service["location"].get("longitude", 0),
                    tech_lat,
                    tech_lon,
                )
                service["distance_km"] = round(distance, 2)
                service["estimated_eta"] = round(estimate_eta_minutes(distance), 0)
    
    return success_response("Pending jobs", services)


@router.post("/services/{service_id}/respond")
def respond_to_job(
    service_id: str,
    payload: JobAcceptReject,
    user=Depends(require_roles("technician")),
):
    """Technician accepts or rejects an assigned job."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Verify technician is assigned to this job
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    if service.get("technician_id") != tech_id:
        raise HTTPException(status_code=403, detail="You are not assigned to this job")
    
    if service.get("status") != "assigned":
        raise HTTPException(status_code=400, detail="Job is not in 'assigned' status")
    
    customer_id = service.get("customer_id")
    
    if payload.action == "accept":
        # Prevent accepting if technician already has another active job
        if is_technician_busy(tech_id, exclude_service_id=object_id):
            raise HTTPException(
                status_code=400,
                detail="Finish your current active job before accepting a new one",
            )

        # Technician accepts the job
        eta = payload.estimated_arrival_minutes or 30
        
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": "accepted",
                    "accepted_at": datetime.utcnow(),
                    "technician_eta_minutes": eta,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        # Notify customer
        if customer_id:
            create_notification(
                recipient_id=customer_id,
                event_type=EventType.STATUS_UPDATE,
                message=f"Technician has accepted your job! ETA: {eta} minutes",
                related_id=str(service_id),
            )
        
        # Check if this technician has other assigned jobs - reassign them
        other_jobs = list(services_collection.find({
            "technician_id": tech_id,
            "status": "assigned",
            "_id": {"$ne": object_id},
            "is_active": True
        }))
        
        reassigned_count = 0
        for other_job in other_jobs:
            # Reassign to another technician
            reassigned = reassign_job_to_new_technician(other_job, exclude_tech_id=tech_id)
            if reassigned:
                reassigned_count += 1
        
        logger.info(f"Job accepted: service_id={service_id}, tech_id={tech_id}, reassigned={reassigned_count}")
        return success_response("Job accepted", {
            "eta_minutes": eta,
            "other_jobs_reassigned": reassigned_count
        })
    
    else:  # reject
        if not payload.reject_reason:
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        # Decrease workload
        technicians_collection.update_one(
            {"_id": ObjectId(tech_id)},
            {"$inc": {"workload": -1, "cancelled_jobs": 1}}
        )
        
        # Clear assignment first before attempting reassignment
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "technician_id": None,
                    "technician_response": "rejected",
                    "status": "pending",
                    "rejection_reason": payload.reject_reason,
                    "updated_at": datetime.utcnow(),
                },
                "$push": {"assignment_history": tech_id},
            }
        )
        
        # Re-fetch the updated service for reassignment
        service = services_collection.find_one({"_id": object_id})
        
        # Try to reassign to another technician
        reassigned = reassign_job_to_new_technician(service, exclude_tech_id=tech_id)
        
        if reassigned:
            # Customer notification handled inside reassign_job_to_new_technician
            logger.info(f"Job rejected and reassigned: service_id={service_id}, old_tech={tech_id}")
            return success_response("Job rejected, reassigned to new technician", {"reassigned": True})
        else:
            # No replacement found, notify customer
            if customer_id:
                create_notification(
                    recipient_id=customer_id,
                    event_type=EventType.STATUS_UPDATE,
                    message="The assigned technician is unavailable. We're finding another technician for you.",
                    related_id=str(service_id),
                )
            
            logger.info(f"Job rejected, no replacement: service_id={service_id}")
            return success_response("Job rejected, searching for new technician", {"reassigned": False})


@router.patch("/services/{service_id}/technician-response")
def technician_response_to_request(
    service_id: str,
    payload: TechnicianResponse,
    user=Depends(require_roles("technician")),
):
    """
    Technician accepts or rejects a job request (new choose-technician flow).
    Works for services in 'awaiting_technician_acceptance' status.
    """
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Verify technician is the requested_technician
    tech_id = user.get("technician_id")
    if not tech_id:
        technician_doc = technicians_collection.find_one({"email": user.get("email")})
        if technician_doc:
            tech_id = str(technician_doc["_id"])
    
    if not tech_id:
        raise HTTPException(status_code=404, detail="Technician not found")
    
    requested_tech = service.get("requested_technician")
    if requested_tech != tech_id:
        raise HTTPException(status_code=403, detail="You are not the requested technician for this job")
    
    if service.get("status") != "awaiting_technician_acceptance":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting technician acceptance (current: {service.get('status')})"
        )
    
    customer_id = service.get("customer_id")
    
    if payload.action == "accept":
        # Prevent accepting if technician already has another active job
        if is_technician_busy(tech_id, exclude_service_id=object_id):
            raise HTTPException(
                status_code=400,
                detail="Finish your current active job before accepting a new one",
            )
        
        eta = payload.estimated_arrival_minutes or 30
        
        # Technician accepts → status becomes "assigned", store technician_id
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": "assigned",
                    "technician_id": tech_id,
                    "technician_response": "accepted",
                    "assigned_at": datetime.utcnow(),
                    "accepted_at": datetime.utcnow(),
                    "technician_eta_minutes": eta,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        
        # Increment technician workload
        technicians_collection.update_one(
            {"_id": ObjectId(tech_id)},
            {"$inc": {"workload": 1}},
        )
        
        # Notify customer
        if customer_id:
            create_notification(
                recipient_id=customer_id,
                event_type=EventType.STATUS_UPDATE,
                message=f"Technician has accepted your job! ETA: {eta} minutes",
                related_id=str(service_id),
            )
        
        logger.info(f"Technician accepted job: service={service_id}, tech={tech_id}")
        return success_response("Job accepted", {
            "service_id": str(service_id),
            "status": "assigned",
            "eta_minutes": eta,
        })
    
    else:  # reject
        if not payload.reject_reason:
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        # Remove rejected technician from suggested list
        suggested = service.get("suggested_technicians", [])
        suggested = [s for s in suggested if s["technician_id"] != tech_id]
        
        # Clear assignment and update technician response
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "technician_id": None,
                    "technician_response": "rejected",
                    "status": "pending",
                    "suggested_technicians": suggested,
                    "rejection_reason": payload.reject_reason,
                    "updated_at": datetime.utcnow(),
                },
                "$push": {"assignment_history": tech_id},
            },
        )
        
        # Increment cancelled_jobs for the technician
        technicians_collection.update_one(
            {"_id": ObjectId(tech_id)},
            {"$inc": {"cancelled_jobs": 1}},
        )
        
        # Auto-suggest next best technician from remaining list
        while suggested:
            next_tech_id = suggested[0]["technician_id"]
            
            # Verify next technician is still available
            next_tech = technicians_collection.find_one({
                "_id": ObjectId(next_tech_id),
                "availability": True,
                "is_active": True,
            })
            
            if next_tech and not is_technician_busy(next_tech_id, exclude_service_id=object_id):
                # Auto-send request to next technician (only set requested_technician, not technician_id)
                services_collection.update_one(
                    {"_id": object_id},
                    {
                        "$set": {
                            "requested_technician": next_tech_id,
                            "technician_response": "pending",
                            "status": "awaiting_technician_acceptance",
                            "assigned_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow(),
                            "suggested_technicians": suggested,
                        }
                    },
                )
                
                # Notify next technician
                create_notification(
                    recipient_id=next_tech_id,
                    event_type=EventType.ASSIGNMENT,
                    message=f"New {service.get('category')} job request! Please accept or reject.",
                    related_id=str(service_id),
                )
                
                # Notify customer about the switch
                if customer_id:
                    create_notification(
                        recipient_id=customer_id,
                        event_type=EventType.STATUS_UPDATE,
                        message="Previous technician unavailable. Next best technician has been suggested.",
                        related_id=str(service_id),
                    )
                
                logger.info(f"Job rejected by {tech_id}, auto-sent to next: {next_tech_id}")
                return success_response("Job rejected, sent to next technician", {
                    "reassigned": True,
                    "next_technician_id": next_tech_id,
                    "next_technician_name": next_tech.get("name"),
                })
            else:
                # This technician not available, remove and try next in loop
                suggested = [s for s in suggested if s["technician_id"] != next_tech_id]
        
        # No more suggested technicians — set back to pending for re-ranking
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": "pending",
                    "requested_technician": None,
                    "technician_response": "pending",
                    "suggested_technicians": [],
                }
            },
        )
        
        if customer_id:
            create_notification(
                recipient_id=customer_id,
                event_type=EventType.STATUS_UPDATE,
                message="Previous technician unavailable. Please choose a new technician or we'll find one for you.",
                related_id=str(service_id),
            )
        
        logger.info(f"Job rejected, no more suggestions: service_id={service_id}")
        return success_response("Job rejected, no more suggested technicians", {"reassigned": False})


def reassign_job_to_new_technician(service: dict, exclude_tech_id: str) -> bool:
    """Reassign a job to a different technician using ML selection."""
    category = service.get("category", "")
    
    # Find available technicians (excluding current one)
    technicians = list(
        technicians_collection.find({
            "availability": True,
            "is_active": True,
            "skills": category,
            "_id": {"$ne": ObjectId(exclude_tech_id)}
        })
    )

    technicians = [
        t for t in technicians if not is_technician_busy(str(t.get("_id")), exclude_service_id=service.get("_id"))
    ]
    
    if not technicians:
        return False
    
    # Use ML to select best technician
    best, best_score, best_components = select_best_technician(
        service, technicians, exclude_ids={exclude_tech_id}
    )
    
    if not best or best_score < 0.3:
        return False
    
    new_tech_id = best.get("_id")
    service_id = service.get("_id")
    
    # Update service: set requested_technician (not technician_id — that's set on accept)
    services_collection.update_one(
        {"_id": service_id},
        {
            "$set": {
                "status": "awaiting_technician_acceptance",
                "requested_technician": str(new_tech_id),
                "technician_response": "pending",
                "assigned_at": datetime.utcnow(),
                "reassigned": True,
                "previous_technician_id": exclude_tech_id,
                "updated_at": datetime.utcnow(),
            },
            "$addToSet": {"assignment_history": exclude_tech_id},
        }
    )
    
    # Notify new technician
    create_notification(
        recipient_id=str(new_tech_id),
        event_type=EventType.ASSIGNMENT,
        message=f"New {category} job assigned to you",
        related_id=str(service_id),
    )
    
    # Notify customer about reassignment
    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.REASSIGNMENT,
            message=f"Your job has been reassigned to a new technician.",
            related_id=str(service_id),
        )
    
    return True


@router.get("/services/{service_id}/suggested-technicians")
def get_suggested_technicians(
    service_id: str,
    user=Depends(require_roles("customer", "admin")),
):
    """
    Get ML-ranked technicians for a service request.
    Returns top technicians sorted by predicted success probability.
    """
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # For customers, only allow viewing their own services
    if user.get("role") == "customer" and service.get("customer_id") != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    category = service.get("category", "")
    
    # Find available technicians with matching skills
    technicians = list(
        technicians_collection.find({
            "availability": True,
            "is_active": True,
            "skills": category
        })
    )
    
    if not technicians:
        return success_response("No available technicians", {"technicians": [], "category": category})
    
    # Score all technicians using ML model
    scored_technicians = []
    for tech in technicians:
        score, components = calculate_score(service, tech)
        scored_technicians.append({
            "id": str(tech.get("_id")),
            "name": tech.get("name"),
            "rating": tech.get("rating", 0),
            "completed_jobs": tech.get("completed_jobs", 0),
            "skills": tech.get("skills", []),
            "score": round(score, 3),
            "predicted_success": round(components.get("predicted_success_probability", 0), 3),
            "prediction_source": components.get("prediction_source", "unknown"),
            "distance_km": round(components.get("distance_km", 0), 2),
            "eta_minutes": round(estimate_eta_minutes(components.get("distance_km", 0)), 0),
        })
    
    # Sort by score descending
    scored_technicians.sort(key=lambda x: x["score"], reverse=True)
    
    # Mark the best one
    if scored_technicians:
        scored_technicians[0]["is_ml_recommended"] = True
    
    return success_response(
        "Suggested technicians retrieved",
        {
            "technicians": scored_technicians,  # Return ALL available technicians
            "ml_recommended": scored_technicians[0] if scored_technicians else None,
            "category": category,
            "total_available": len(technicians),
        }
    )


@router.get("/admin/jobs")
def list_all_jobs(user=Depends(require_roles("admin"))):
    jobs = []
    for item in services_collection.find({"is_active": True}):
        item["_id"] = str(item.get("_id"))
        jobs.append(item)
    return success_response("Jobs retrieved", jobs)


@router.post("/services/{service_id}/assign")
def auto_assign_technician(
    service_id: str,
    user=Depends(require_roles("admin")),
):
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail="Service must be in pending status to assign",
        )

    technicians = list(
        technicians_collection.find({"availability": True, "is_active": True})
    )
    if not technicians:
        raise HTTPException(status_code=404, detail="No available technicians")

    best, best_score, best_components = select_best_technician(service, technicians)

    if not best:
        raise HTTPException(status_code=404, detail="No eligible technician found")

    best_id = best.get("_id")
    result = services_collection.update_one(
        {"_id": object_id, "status": "pending"},
        {
            "$set": {
                "status": "assigned",
                "technician_id": str(best_id),
                "assigned_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Service already assigned (race condition prevention)",
        )

    technicians_collection.update_one(
        {"_id": best_id},
        {"$inc": {"workload": 1}},
    )

    service_location = service.get("location", {})
    best_lat, best_lon, _ = resolve_technician_coordinates(best)
    distance_km = haversine_distance_km(
        service_location.get("latitude", 0.0),
        service_location.get("longitude", 0.0),
        best_lat,
        best_lon,
    )
    eta_minutes = estimate_eta_minutes(distance_km)
    services_collection.update_one(
        {"_id": object_id},
        {"$set": {"eta_minutes": eta_minutes}},
    )

    create_notification(
        recipient_id=str(best_id),
        event_type=EventType.ASSIGNMENT,
        message="New job assigned to you",
        related_id=str(service.get("_id")),
    )

    logger.log_assignment(str(object_id), str(best_id), best_score)
    return success_response(
        "Technician assigned",
        {
            "technician_id": str(best_id),
            "score": best_score,
            "score_components": best_components,
            "eta_minutes": eta_minutes,
        },
    )


@router.post("/services/{service_id}/rate")
def rate_service(
    service_id: str,
    payload: ServiceRating,
    user=Depends(require_roles("customer")),
):
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.get("customer_id") != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if service.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    technician_id = service.get("technician_id")
    if not technician_id:
        raise HTTPException(status_code=400, detail="No technician assigned")

    technician = technicians_collection.find_one({
        "_id": ObjectId(technician_id),
        "is_active": True,
    })
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")

    completed_jobs = int(technician.get("completed_jobs", 0) or 0)
    current_rating = float(technician.get("rating", 0.0) or 0.0)
    new_rating = (current_rating * completed_jobs + payload.rating) / (
        completed_jobs + 1
    )

    technicians_collection.update_one(
        {"_id": ObjectId(technician_id)},
        {
            "$set": {"rating": new_rating},
            "$inc": {"completed_jobs": 1, "workload": -1},
        },
    )

    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "rated",
                "rating": payload.rating,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    create_notification(
        recipient_id=str(technician_id),
        event_type=EventType.RATING,
        message=f"You received a {payload.rating}/5 rating",
        related_id=str(service.get("_id")),
    )

    logger.info(f"Rating submitted: service_id={service_id}, rating={payload.rating}")
    return success_response("Rating submitted", {"rating": payload.rating})


@router.post("/services/{service_id}/technician-cancel")
def technician_cancel_service(
    service_id: str,
    user=Depends(require_roles("technician")),
):
    """Technician cancels an active job assigned to them."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    technician_id = service.get("technician_id")
    if technician_id and technician_id != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if service.get("status") in {"completed", "rated", "cancelled"}:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")

    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_by": user.get("_id"),
                "updated_at": datetime.utcnow(),
            }
        },
    )

    technicians_collection.update_one(
        {"_id": ObjectId(user.get("_id"))},
        {
            "$inc": {"cancelled_jobs": 1, "workload": -1},
        },
    )

    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.CANCELLATION,
            message="Job cancelled by technician",
            related_id=str(service.get("_id")),
        )

    logger.info(f"Job cancelled by technician: service_id={service_id}, tech_id={user.get('_id')}")
    return success_response("Job cancelled")


@router.post("/services/{service_id}/pay")
def process_payment(
    service_id: str,
    payload: PaymentRequest,
    user=Depends(require_roles("customer")),
):
    """
    Process payment for a completed service.
    
    Payment statuses: pending -> paid/failed -> refunded
    """
    import uuid
    
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.get("customer_id") != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if service.get("status") not in {"completed", "rated"}:
        raise HTTPException(
            status_code=400,
            detail="Service must be completed before payment",
        )

    current_payment_status = service.get("payment_status", "pending")
    if current_payment_status == "paid":
        raise HTTPException(status_code=400, detail="Service already paid")

    # Generate internal payment ID if not provided by gateway
    payment_id = payload.transaction_id or f"PAY-{uuid.uuid4().hex[:12].upper()}"
    
    # Mock payment processing (in production, integrate with payment gateway)
    # Simulate success for demo - in real implementation, call payment gateway API
    payment_success = True  # Would be from gateway response
    
    if payment_success:
        payment_status = "paid"
        
        # Store payment record
        payment_record = {
            "payment_id": payment_id,
            "service_id": str(object_id),
            "customer_id": user.get("_id"),
            "amount": service.get("final_price") or service.get("estimated_price", 0),
            "payment_method": payload.payment_method,
            "status": "completed",
            "created_at": datetime.utcnow(),
        }
        payments_collection.insert_one(payment_record)
        
        # Update service with payment info
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "payment_status": payment_status,
                    "payment_id": payment_id,
                    "paid_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        
        logger.info(f"Payment processed: service_id={service_id}, payment_id={payment_id}")
        return success_response(
            "Payment successful",
            {
                "payment_id": payment_id,
                "amount": payment_record["amount"],
                "status": payment_status,
            },
        )
    else:
        services_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "payment_status": "failed",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise HTTPException(status_code=402, detail="Payment failed")


@router.post("/services/{service_id}/refund")
def process_refund(
    service_id: str,
    payload: RefundRequest,
    user=Depends(require_roles("admin")),
):
    """
    Process refund for a paid service. Admin only.
    """
    import uuid
    
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({
        "_id": object_id,
        "is_active": True,
    })
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service.get("payment_status") != "paid":
        raise HTTPException(status_code=400, detail="Service not paid or already refunded")

    original_amount = service.get("final_price") or service.get("estimated_price", 0)
    refund_amount = payload.amount if payload.amount else original_amount
    
    if refund_amount > original_amount:
        raise HTTPException(status_code=400, detail="Refund amount exceeds paid amount")

    refund_id = f"REF-{uuid.uuid4().hex[:12].upper()}"
    
    # Store refund record
    refund_record = {
        "refund_id": refund_id,
        "payment_id": service.get("payment_id"),
        "service_id": str(object_id),
        "customer_id": service.get("customer_id"),
        "original_amount": original_amount,
        "refund_amount": refund_amount,
        "reason": payload.reason,
        "status": "completed",
        "processed_by": user.get("_id"),
        "created_at": datetime.utcnow(),
    }
    payments_collection.insert_one(refund_record)
    
    # Update service payment status
    new_status = "refunded" if refund_amount == original_amount else "partial_refund"
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "payment_status": new_status,
                "refund_id": refund_id,
                "refund_amount": refund_amount,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    
    logger.info(f"Refund processed: service_id={service_id}, refund_id={refund_id}, amount={refund_amount}")
    return success_response(
        "Refund processed",
        {
            "refund_id": refund_id,
            "amount": refund_amount,
            "status": new_status,
        },
    )
