# User model definitions go here.
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Literal, Optional

class UserRegister(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Literal["customer", "technician", "admin"]

    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    phone: Optional[str] = None
    address: Optional[str] = None


class UserProfileResponse(BaseModel):
    role: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None