from datetime import datetime, timedelta
from typing import Tuple

from database import services_collection, technicians_collection
from utils.notification_utils import create_notification, EventType
from utils.technician_selection import select_best_technician


def reassign_stale_jobs(stale_minutes: int = 5) -> Tuple[int, int]:
    cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
    stale = list(
        services_collection.find(
            {
                "status": {"$in": ["assigned", "awaiting_technician_acceptance"]},
                "assigned_at": {"$lt": cutoff},
                "is_active": True,
            }
        )
    )
    reassigned = 0
    attempted = len(stale)

    for service in stale:
        technicians = list(technicians_collection.find({"availability": True, "is_active": True}))
        old_tech_id = service.get("technician_id") or service.get("requested_technician")
        exclude_ids = {old_tech_id} if old_tech_id else set()
        best, _, _ = select_best_technician(service, technicians, exclude_ids=exclude_ids)
        if not best:
            continue

        old_tech_id = service.get("technician_id") or service.get("requested_technician")
        services_collection.update_one(
            {"_id": service.get("_id")},
            {
                "$set": {
                    "technician_id": None,
                    "requested_technician": str(best.get("_id")),
                    "technician_response": "pending",
                    "status": "awaiting_technician_acceptance",
                    "assigned_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
                "$addToSet": {"assignment_history": old_tech_id},
            },
        )

        create_notification(
            recipient_id=str(best.get("_id")),
            event_type=EventType.REASSIGNMENT,
            message="Job reassigned to you",
            related_id=str(service.get("_id")),
        )

        # Notify customer about reassignment
        customer_id = service.get("customer_id")
        if customer_id:
            create_notification(
                recipient_id=customer_id,
                event_type=EventType.STATUS_UPDATE,
                message="Your job has been reassigned to a new technician.",
                related_id=str(service.get("_id")),
            )

        reassigned += 1

    return reassigned, attempted
