# User route handlers go here.
from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError
from database import users_collection
from models.user_model import UserRegister, UserLogin
from utils.password_utils import hash_password, verify_password
from utils.jwt_utils import create_access_token
from utils.auth_utils import require_roles
from utils.rate_limit import is_rate_limited, reset_rate_limit
from utils.response_utils import success_response, error_response
from utils.logger import logger

router = APIRouter()

@router.post("/register")
def register_user(user: UserRegister):
    try:
        hashed_pw = hash_password(user.password)
        user_data = {
            "name": user.name,
            "email": user.email,
            "password": hashed_pw,
            "role": user.role,
            "is_active": True,
        }
        users_collection.insert_one(user_data)
        return success_response("User registered successfully")
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")


@router.post("/login")
def login_user(credentials: UserLogin, request: Request):
    client_ip = request.client.host
    
    if is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    
    user = users_collection.find_one({"email": credentials.email, "is_active": True})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(credentials.password, user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    reset_rate_limit(client_ip)
    token = create_access_token(
        subject=str(user.get("_id")),
        email=user.get("email", ""),
        role=user.get("role", ""),
    )

    logger.info(f"User login: email={user.get('email')}")
    return success_response(
        "Login successful",
        {"access_token": token, "token_type": "bearer", "role": user.get("role", "")},
    )


@router.get("/admin/users")
def list_all_users(user=Depends(require_roles("admin"))):
    users = []
    for item in users_collection.find({"is_active": True}, {"password": 0}):
        item["_id"] = str(item.get("_id"))
        users.append(item)
    logger.info(f"Admin listed users: count={len(users)}")
    return success_response("Users retrieved", users)