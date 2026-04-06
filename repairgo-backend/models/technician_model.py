# Technician model definitions go here.
from pydantic import BaseModel, Field, validator, EmailStr
from typing import List, Optional
from datetime import datetime


class TechnicianRegister(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    skills: List[str]
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    bank_details: Optional[dict] = None
    experience_years: int = Field(ge=0, default=0)
    availability: bool = True
    workload: int = Field(ge=0, default=0)
    latitude: float = Field(ge=-90, le=90, default=0.0)
    longitude: float = Field(ge=-180, le=180, default=0.0)
    # Home/base location captured at registration. Live location will update latitude/longitude,
    # but these provide a reliable fallback if live data is stale.
    home_latitude: float = Field(ge=-90, le=90, default=0.0)
    home_longitude: float = Field(ge=-180, le=180, default=0.0)
    rating: float = Field(ge=0, le=5, default=0.0)
    completed_jobs: int = Field(ge=0, default=0)
    earnings: float = Field(ge=0, default=0.0)

    @validator("skills")
    def skills_not_empty(cls, v):
        if not v:
            raise ValueError("Technician must have at least one skill")
        return v

    @validator("upi_id")
    def validate_upi_id(cls, v):
        if v is None:
            return v
        normalized = v.strip()
        if not normalized:
            raise ValueError("UPI ID cannot be empty")
        if "@" not in normalized:
            raise ValueError("UPI ID must contain '@'")
        return normalized


class TechnicianLocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class TechnicianLiveLocationUpdate(BaseModel):
    """Enhanced location update for live tracking (like Ola/Rapido)."""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    heading: Optional[float] = Field(None, ge=0, le=360)  # Direction in degrees
    speed_kmh: Optional[float] = Field(None, ge=0)  # Current speed
    accuracy_meters: Optional[float] = None  # GPS accuracy
    is_navigating: bool = False  # True if actively on the way to a job
    active_job_id: Optional[str] = None  # Current job being worked on


class TechnicianAvailabilityUpdate(BaseModel):
    """Update technician availability status."""
    availability: bool
    reason: Optional[str] = None  # Reason for going offline


class TechnicianProfileUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[List[str]] = None
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    experience_years: Optional[int] = Field(default=None, ge=0)
    bank_details: Optional[dict] = None

    @validator("upi_id")
    def validate_profile_upi_id(cls, v):
        if v is None:
            return v
        normalized = v.strip()
        if not normalized:
            raise ValueError("UPI ID cannot be empty")
        if "@" not in normalized:
            raise ValueError("UPI ID must contain '@'")
        return normalized
