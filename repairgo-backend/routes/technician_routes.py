# Technician route handlers go here.
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from database import technicians_collection, categories_collection, services_collection, users_collection, payments_collection
from models.technician_model import (
    TechnicianRegister, 
    TechnicianLocationUpdate, 
    TechnicianLiveLocationUpdate,
    TechnicianAvailabilityUpdate,
)
from utils.auth_utils import require_roles
from utils.response_utils import success_response
from utils.logger import logger
from utils.password_utils import hash_password
from utils.notification_utils import create_notification, EventType
from utils.technician_selection import haversine_distance_km, estimate_eta_minutes

router = APIRouter()
PREDEFINED_CATEGORIES = set()


def load_categories():
    global PREDEFINED_CATEGORIES
    PREDEFINED_CATEGORIES = set(
        cat["name"] for cat in categories_collection.find({})
    )


@router.post("/register-technician")
def register_technician(tech: TechnicianRegister):
    try:
        tech_data = tech.dict()
        # Hash password and store separately
        hashed_password = hash_password(tech_data.pop("password"))
        # Capture home/base location from registration so we can fall back if live location is stale
        if not tech_data.get("home_latitude"):
            tech_data["home_latitude"] = tech_data.get("latitude", 0.0)
        if not tech_data.get("home_longitude"):
            tech_data["home_longitude"] = tech_data.get("longitude", 0.0)
        tech_data["is_active"] = True
        tech_data["cancelled_jobs"] = 0
        tech_data["is_verified"] = False
        tech_data["total_ratings"] = 0
        tech_data.setdefault("phone", "")
        tech_data.setdefault("upi_id", "")
        tech_data.setdefault("bank_details", {})
        tech_data.setdefault("earnings", 0.0)
        
        # Insert into technicians collection
        result = technicians_collection.insert_one(tech_data)
        
        # Also create user account for login
        user_data = {
            "name": tech.name,
            "email": tech.email,
            "password": hashed_password,
            "role": "technician",
            "phone": tech.phone or "",
            "address": "",
            "wallet_balance": 0.0,
            "is_active": True,
            "technician_id": str(result.inserted_id),
        }
        users_collection.insert_one(user_data)
        
        logger.info(f"Technician registered: email={tech.email}")
        return success_response("Technician registered successfully")
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")


@router.patch("/technicians/location")
def update_technician_location(
    payload: TechnicianLocationUpdate,
    user=Depends(require_roles("technician")),
):
    # Get technician_id from user record, or use email to find technician
    tech_id = user.get("technician_id")
    if tech_id:
        result = technicians_collection.update_one(
            {"_id": ObjectId(tech_id), "is_active": True},
            {"$set": {"latitude": payload.latitude, "longitude": payload.longitude}},
        )
    else:
        # Fallback: find technician by email
        result = technicians_collection.update_one(
            {"email": user.get("email"), "is_active": True},
            {"$set": {"latitude": payload.latitude, "longitude": payload.longitude}},
        )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Technician not found")

    logger.info(f"Technician location updated: user_email={user.get('email')}")
    return success_response("Location updated")


@router.get("/technicians/me")
def get_current_technician(user=Depends(require_roles("technician"))):
    """Get current technician's profile."""
    tech_id = user.get("technician_id")
    if tech_id:
        technician = technicians_collection.find_one({"_id": ObjectId(tech_id)})
    else:
        technician = technicians_collection.find_one({"email": user.get("email")})
    
    if not technician:
        raise HTTPException(status_code=404, detail="Technician profile not found")
    
    technician["_id"] = str(technician["_id"])
    return success_response("Technician profile", technician)


@router.get("/technicians/my-jobs")
def get_my_jobs(user=Depends(require_roles("technician"))):
    """Get jobs assigned to the current technician."""
    tech_id = user.get("technician_id")
    if tech_id:
        technician = technicians_collection.find_one({"_id": ObjectId(tech_id)})
    else:
        technician = technicians_collection.find_one({"email": user.get("email")})
    
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    
    # Find ALL services assigned to this technician (active + completed history)
    tech_id_str = str(technician["_id"])
    services = list(services_collection.find({
        "$or": [
            {"technician_id": tech_id_str},
            {"requested_technician": tech_id_str},
        ],
        "is_active": {"$ne": False},
    }).sort("updated_at", -1))
    
    for service in services:
        service["_id"] = str(service["_id"])
    
    return success_response("Technician jobs", services)


# ============================================================================
# Live Location Tracking (Ola/Rapido style)
# ============================================================================

@router.patch("/technicians/live-location")
def update_live_location(
    payload: TechnicianLiveLocationUpdate,
    user=Depends(require_roles("technician")),
):
    """
    Update technician's live location with enhanced tracking data.
    Called frequently when technician is navigating to a job.
    """
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    if not tech_id:
        raise HTTPException(status_code=404, detail="Technician not found")
    
    update_data = {
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "last_location_update": datetime.utcnow(),
    }
    
    if payload.heading is not None:
        update_data["heading"] = payload.heading
    if payload.speed_kmh is not None:
        update_data["speed_kmh"] = payload.speed_kmh
    if payload.accuracy_meters is not None:
        update_data["location_accuracy"] = payload.accuracy_meters
    update_data["is_navigating"] = payload.is_navigating
    
    technicians_collection.update_one(
        {"_id": ObjectId(tech_id)},
        {"$set": update_data}
    )
    
    # If navigating to a job, update ETA for that job
    if payload.is_navigating and payload.active_job_id:
        try:
            job_id = ObjectId(payload.active_job_id)
            service = services_collection.find_one({"_id": job_id})
            if service and service.get("location"):
                distance = haversine_distance_km(
                    payload.latitude,
                    payload.longitude,
                    service["location"].get("latitude", 0),
                    service["location"].get("longitude", 0),
                )
                # Use actual speed if available, otherwise assume 30 km/h
                speed = payload.speed_kmh if payload.speed_kmh and payload.speed_kmh > 0 else 30
                eta_minutes = (distance / speed) * 60
                
                services_collection.update_one(
                    {"_id": job_id},
                    {"$set": {
                        "live_eta_minutes": round(eta_minutes, 0),
                        "technician_distance_km": round(distance, 2),
                        "eta_updated_at": datetime.utcnow(),
                    }}
                )
        except Exception as e:
            logger.error(f"Error updating job ETA: {e}")
    
    return success_response("Location updated")


@router.patch("/technicians/availability")
def update_availability(
    payload: TechnicianAvailabilityUpdate,
    user=Depends(require_roles("technician")),
):
    """Update technician availability (go online/offline)."""
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    if not tech_id:
        raise HTTPException(status_code=404, detail="Technician not found")
    
    update_data = {
        "availability": payload.availability,
        "availability_updated_at": datetime.utcnow(),
    }
    
    if payload.reason:
        update_data["unavailability_reason"] = payload.reason
    
    technicians_collection.update_one(
        {"_id": ObjectId(tech_id)},
        {"$set": update_data}
    )
    
    status = "online" if payload.availability else "offline"
    logger.info(f"Technician {tech_id} went {status}")
    
    return success_response(f"You are now {status}")


@router.post("/technicians/start-navigation/{service_id}")
def start_navigation(
    service_id: str,
    user=Depends(require_roles("technician")),
):
    """Technician starts navigating to a job (updates status to on_the_way)."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("technician_id") != tech_id:
        raise HTTPException(status_code=403, detail="Not assigned to this job")
    
    if service.get("status") not in ["accepted", "assigned"]:
        raise HTTPException(status_code=400, detail="Job must be accepted first")
    
    # Get technician location for ETA calculation
    technician = technicians_collection.find_one({"_id": ObjectId(tech_id)})
    if technician and service.get("location"):
        distance = haversine_distance_km(
            technician.get("latitude", 0),
            technician.get("longitude", 0),
            service["location"].get("latitude", 0),
            service["location"].get("longitude", 0),
        )
        eta_minutes = estimate_eta_minutes(distance)
    else:
        eta_minutes = 30
        distance = 0
    
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "on_the_way",
                "navigation_started_at": datetime.utcnow(),
                "live_eta_minutes": eta_minutes,
                "technician_distance_km": round(distance, 2),
                "updated_at": datetime.utcnow(),
            }
        }
    )
    
    # Mark technician as navigating
    technicians_collection.update_one(
        {"_id": ObjectId(tech_id)},
        {"$set": {"is_navigating": True, "active_job_id": service_id}}
    )
    
    # Notify customer
    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.STATUS_UPDATE,
            message=f"Technician is on the way! ETA: {int(eta_minutes)} minutes",
            related_id=service_id,
        )
    
    return success_response("Navigation started", {
        "eta_minutes": eta_minutes,
        "distance_km": round(distance, 2)
    })


@router.post("/technicians/arrive/{service_id}")
def arrive_at_job(
    service_id: str,
    user=Depends(require_roles("technician")),
):
    """Technician arrives at job location (updates status to in_progress)."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("technician_id") != tech_id:
        raise HTTPException(status_code=403, detail="Not assigned to this job")
    
    if service.get("status") != "on_the_way":
        raise HTTPException(status_code=400, detail="Must be 'on the way' first")
    
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "in_progress",
                "arrived_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        }
    )
    
    # Mark technician as no longer navigating
    technicians_collection.update_one(
        {"_id": ObjectId(tech_id)},
        {"$set": {"is_navigating": False, "active_job_id": None}}
    )
    
    # Notify customer
    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.STATUS_UPDATE,
            message="Technician has arrived and started working!",
            related_id=service_id,
        )
    
    return success_response("Arrived at job, work started")


@router.post("/technicians/complete/{service_id}")
def complete_job(
    service_id: str,
    user=Depends(require_roles("technician")),
):
    """Technician completes a job."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    tech_id = user.get("technician_id")
    if not tech_id:
        technician = technicians_collection.find_one({"email": user.get("email")})
        if technician:
            tech_id = str(technician["_id"])
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("technician_id") != tech_id:
        raise HTTPException(status_code=403, detail="Not assigned to this job")
    
    if service.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Job must be in progress")
    
    services_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        }
    )
    
    # Update technician stats
    technicians_collection.update_one(
        {"_id": ObjectId(tech_id)},
        {
            "$inc": {"completed_jobs": 1, "workload": -1},
            "$set": {"is_navigating": False, "active_job_id": None}
        }
    )
    
    # Notify customer
    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.STATUS_UPDATE,
            message="Job completed! Please rate your technician.",
            related_id=service_id,
        )
    
    return success_response("Job completed successfully")


# ============================================================================
# Customer-facing endpoint: Get technician live location
# ============================================================================

@router.get("/services/{service_id}/technician-location")
def get_technician_live_location(
    service_id: str,
    user=Depends(require_roles("customer")),
):
    """Get live location of assigned technician for tracking."""
    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")
    
    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if service.get("customer_id") != user.get("_id"):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    technician_id = service.get("technician_id")
    if not technician_id:
        raise HTTPException(status_code=404, detail="No technician assigned")
    
    # Only allow tracking when technician is on the way or status is accepted
    trackable_statuses = ["accepted", "on_the_way", "in_progress"]
    if service.get("status") not in trackable_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Tracking not available for status: {service.get('status')}"
        )
    
    technician = technicians_collection.find_one({"_id": ObjectId(technician_id)})
    if not technician:
        raise HTTPException(status_code=404, detail="Technician not found")
    
    # Calculate current distance and ETA
    if service.get("location"):
        distance = haversine_distance_km(
            technician.get("latitude", 0),
            technician.get("longitude", 0),
            service["location"].get("latitude", 0),
            service["location"].get("longitude", 0),
        )
        # Use technician's actual speed if available
        speed = technician.get("speed_kmh") if technician.get("speed_kmh", 0) > 0 else 30
        eta_minutes = (distance / speed) * 60
    else:
        distance = 0
        eta_minutes = service.get("live_eta_minutes", 0)
    
    return success_response("Technician location", {
        "technician_name": technician.get("name"),
        "latitude": technician.get("latitude"),
        "longitude": technician.get("longitude"),
        "heading": technician.get("heading"),
        "speed_kmh": technician.get("speed_kmh"),
        "is_navigating": technician.get("is_navigating", False),
        "last_updated": technician.get("last_location_update"),
        "distance_km": round(distance, 2),
        "eta_minutes": round(eta_minutes, 0),
        "service_status": service.get("status"),
    })


@router.post("/technicians/confirm-payment/{service_id}")
def confirm_payment_received(
    service_id: str,
    payload: dict,
    user=Depends(require_roles("technician")),
):
    """Assigned technician confirms customer-marked payment receipt."""
    if not payload.get("technician_confirmed"):
        raise HTTPException(status_code=400, detail="technician_confirmed=true is required")

    try:
        object_id = ObjectId(service_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid service id")

    service = services_collection.find_one({"_id": object_id, "is_active": True})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    tech_id = user.get("technician_id")
    if not tech_id:
        technician_doc = technicians_collection.find_one({"email": user.get("email")})
        if technician_doc:
            tech_id = str(technician_doc["_id"])

    if not tech_id:
        raise HTTPException(status_code=404, detail="Technician not found")

    if service.get("technician_id") != tech_id:
        raise HTTPException(status_code=403, detail="Only assigned technician can confirm payment")

    if service.get("payment_method") != "upi":
        raise HTTPException(status_code=400, detail="Only UPI payments need technician confirmation")

    if not service.get("customer_paid"):
        raise HTTPException(status_code=400, detail="Customer has not marked payment yet")

    if service.get("technician_confirmed"):
        raise HTTPException(status_code=400, detail="Payment already confirmed")

    amount = float(service.get("final_price") or service.get("estimated_price") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    result = services_collection.update_one(
        {"_id": object_id, "technician_confirmed": {"$ne": True}},
        {
            "$set": {
                "technician_confirmed": True,
                "payment_status": "paid",
                "payment_time": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=400, detail="Payment already confirmed")

    technicians_collection.update_one(
        {"_id": ObjectId(tech_id)},
        {"$inc": {"earnings": amount}},
    )

    payments_collection.update_one(
        {"service_id": str(object_id), "payment_method": "upi"},
        {
            "$set": {
                "status": "paid",
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {
                "service_id": str(object_id),
                "customer_id": service.get("customer_id"),
                "technician_id": tech_id,
                "amount": amount,
                "payment_method": "upi",
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )

    customer_id = service.get("customer_id")
    if customer_id:
        create_notification(
            recipient_id=customer_id,
            event_type=EventType.PAYMENT,
            message="Technician confirmed your UPI payment. Marked as paid.",
            related_id=service_id,
        )

    return success_response("Payment confirmed", {"payment_status": "paid", "technician_confirmed": True})