import os
from datetime import datetime, timedelta

import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters long")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))


def create_access_token(subject: str, email: str, role: str) -> str:
    expires_at = datetime.utcnow() + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
