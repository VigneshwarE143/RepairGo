from pydantic import BaseModel, conint, Field
from typing import Literal, Optional, List


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ServiceCreate(BaseModel):
    category: str
    description: str
    location: Location
    urgency: Literal["low", "medium", "high"]
    payment_method: Optional[Literal["cash", "upi", "card"]] = None
    payment_status: str = "pending"
    customer_paid: bool = False
    technician_confirmed: bool = False
    payment_time: Optional[str] = None


class PaymentRequest(BaseModel):
    """Payment request payload."""
    payment_method: Literal["cash", "upi", "card"] = "upi"
    customer_paid: bool = False
    technician_confirmed: bool = False
    transaction_id: Optional[str] = None  # External payment gateway ID
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None


class ServiceEstimate(BaseModel):
    category: str
    location: Location
    urgency: Literal["low", "medium", "high"]


class ServiceStatusUpdate(BaseModel):
    status: Literal[
        "pending",
        "awaiting_technician_acceptance",
        "assigned",
        "accepted",
        "on_the_way",
        "in_progress",
        "completed",
        "rated",
        "cancelled",
    ]


class ServiceRating(BaseModel):
    rating: conint(ge=1, le=5)


class RefundRequest(BaseModel):
    """Refund request payload."""
    reason: str
    amount: Optional[float] = None  # Partial refund, None for full refund


# ============================================================================
# New Models for Cancel & Accept/Reject Flow
# ============================================================================

class ServiceCancelRequest(BaseModel):
    """Cancel booking request with reason."""
    reason: Literal[
        "changed_mind",
        "found_another_service",
        "technician_too_far",
        "price_too_high",
        "emergency_resolved",
        "scheduling_conflict",
        "other"
    ]
    additional_notes: Optional[str] = None


class JobAcceptReject(BaseModel):
    """Technician accept/reject a job."""
    action: Literal["accept", "reject"]
    reject_reason: Optional[Literal[
        "too_far",
        "busy_with_other_job",
        "out_of_service_area",
        "equipment_unavailable",
        "personal_emergency",
        "other"
    ]] = None
    estimated_arrival_minutes: Optional[int] = None  # Required when accepting


class ChooseTechnician(BaseModel):
    """Customer chooses a technician from the suggested list."""
    technician_id: str


class TechnicianResponse(BaseModel):
    """Technician accepts or rejects a requested job."""
    action: Literal["accept", "reject"]
    reject_reason: Optional[Literal[
        "too_far",
        "busy_with_other_job",
        "out_of_service_area",
        "equipment_unavailable",
        "personal_emergency",
        "other"
    ]] = None
    estimated_arrival_minutes: Optional[int] = None  # Required when accepting


class TechnicianLocationUpdate(BaseModel):
    """Live location update from technician."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    heading: Optional[float] = None  # Direction in degrees (0-360)
    speed_kmh: Optional[float] = None  # Current speed
    is_navigating: bool = False  # True if actively going to a job

