# User model definitions go here.
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Literal

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