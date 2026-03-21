from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from bson import ObjectId

from database import users_collection
from utils.jwt_utils import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        return decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user_record(payload: dict = Depends(get_current_user)) -> dict:
    user_id = payload.get("sub", "")
    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = users_collection.find_one({"_id": object_id}, {"password": 0})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user["_id"] = str(user.get("_id"))
    return user


def require_roles(*roles: str):
    def role_checker(user: dict = Depends(get_current_user_record)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return role_checker
