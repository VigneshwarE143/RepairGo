from typing import Optional, Any, Dict
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


def success_response(message: str, data: Optional[Any] = None) -> Dict:
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_response(message: str, data: Optional[Any] = None) -> Dict:
    return {
        "success": False,
        "message": message,
        "data": data,
    }
