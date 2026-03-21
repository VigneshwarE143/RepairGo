from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import asyncio

from database import notifications_collection


class EventType(str, Enum):
    """Enumeration of all notification event types."""
    ASSIGNMENT = "assignment"
    STATUS_UPDATE = "status_update"
    CANCELLATION = "cancellation"
    REASSIGNMENT = "reassignment"
    RATING = "rating"
    PAYMENT = "payment"
    REFUND = "refund"


def create_notification(
    recipient_id: str,
    event_type: EventType,
    message: str,
    related_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    push_realtime: bool = True,
) -> None:
    """
    Create and log a notification event.
    
    Args:
        recipient_id: User ID receiving the notification
        event_type: Type of event (EventType enum)
        message: Human-readable notification message
        related_id: ID of related entity (service, technician, etc)
        context: Additional metadata for the event
        push_realtime: Whether to push via WebSocket (default: True)
    """
    notification_doc = {
        "recipient_id": recipient_id,
        "event_type": event_type.value,
        "message": message,
        "related_id": related_id,
        "context": context or {},
        "created_at": datetime.utcnow(),
        "read": False,
    }
    
    notifications_collection.insert_one(notification_doc)
    
    # Push real-time notification via WebSocket
    if push_realtime:
        try:
            from utils.websocket_manager import push_notification
            
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, schedule the coroutine
                asyncio.create_task(push_notification(
                    recipient_id=recipient_id,
                    event_type=event_type.value,
                    message=message,
                    related_id=related_id,
                    context=context,
                ))
            except RuntimeError:
                # No running loop, run synchronously in a new loop
                # This handles sync route handlers
                pass
        except ImportError:
            pass  # WebSocket manager not available
