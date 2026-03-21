from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional


class CategoryCreate(BaseModel):
    name: str
    base_price: float = Field(ge=0)
    travel_rate: float = Field(ge=0)
    urgency_addon_low: float = Field(ge=0)
    urgency_addon_medium: float = Field(ge=0)
    urgency_addon_high: float = Field(ge=0)

    @validator("name")
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Category name cannot be empty")
        return v.strip()
