from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from database import users_collection, technicians_collection
from utils.payment_utils import validate_upi_id
from utils.auth_utils import require_roles
from utils.password_utils import verify_password
from utils.response_utils import success_response

router = APIRouter()


@router.get("/profile")
def get_profile(user=Depends(require_roles("customer", "technician", "admin"))):
    role = user.get("role")

    if role == "technician":
        tech_id = user.get("technician_id")
        technician = None
        if tech_id:
            try:
                technician = technicians_collection.find_one({"_id": ObjectId(tech_id), "is_active": True})
            except Exception:
                technician = None
        if not technician:
            technician = technicians_collection.find_one({"email": user.get("email"), "is_active": True})
        if not technician:
            raise HTTPException(status_code=404, detail="Technician profile not found")

        return success_response(
            "Profile retrieved",
            {
                "role": "technician",
                "name": technician.get("name", ""),
                "email": technician.get("email", ""),
                "skills": technician.get("skills", []),
                "phone": technician.get("phone", ""),
                "upi_id": technician.get("upi_id", ""),
                "experience_years": technician.get("experience_years", 0),
                "bank_details": technician.get("bank_details", {}),
                "earnings": technician.get("earnings", 0.0),
            },
        )

    # customer/admin profile from users collection
    user_record = users_collection.find_one({"_id": ObjectId(user.get("_id")), "is_active": True}, {"password": 0})
    if not user_record:
        raise HTTPException(status_code=404, detail="Profile not found")

    return success_response(
        "Profile retrieved",
        {
            "role": user_record.get("role"),
            "name": user_record.get("name", ""),
            "email": user_record.get("email", ""),
            "phone": user_record.get("phone", ""),
            "address": user_record.get("address", ""),
            "wallet_balance": user_record.get("wallet_balance", 0.0),
        },
    )


@router.patch("/profile")
def update_profile(
    payload: dict | None = None,
    user=Depends(require_roles("customer", "technician", "admin")),
):
    role = user.get("role")
    payload = payload or {}

    # Protect profile edits by requiring password re-verification.
    user_record = users_collection.find_one(
        {"_id": ObjectId(user.get("_id")), "is_active": True},
        {"password": 1},
    )
    if not user_record:
        raise HTTPException(status_code=404, detail="User account not found")

    current_password = str(payload.get("current_password") or "")
    if not current_password:
        raise HTTPException(status_code=400, detail="Current password is required")

    if not verify_password(current_password, user_record.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid current password")

    if role == "technician":
        allowed_fields = {"name", "skills", "phone", "upi_id", "experience_years", "bank_details"}
        update_data = {k: v for k, v in payload.items() if k in allowed_fields and v is not None}

        if "skills" in update_data and not update_data["skills"]:
            raise HTTPException(status_code=400, detail="skills cannot be empty")

        if "upi_id" in update_data:
            try:
                update_data["upi_id"] = validate_upi_id(update_data["upi_id"])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        if not update_data:
            return success_response("No changes submitted", {})

        tech_id = user.get("technician_id")
        technician_query = None
        if tech_id:
            try:
                technician_query = {"_id": ObjectId(tech_id), "is_active": True}
            except Exception:
                technician_query = None

        if not technician_query:
            technician_query = {"email": user.get("email"), "is_active": True}

        result = technicians_collection.update_one(technician_query, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Technician profile not found")

        # Keep user name/phone in sync for technician account card data
        sync_updates = {}
        if "name" in update_data:
            sync_updates["name"] = update_data["name"]
        if "phone" in update_data:
            sync_updates["phone"] = update_data["phone"]
        if sync_updates:
            users_collection.update_one({"_id": ObjectId(user.get("_id"))}, {"$set": sync_updates})

        return success_response("Profile updated")

    allowed_fields = {"name", "phone", "address"}
    update_data = {k: v for k, v in payload.items() if k in allowed_fields and v is not None}
    if not update_data:
        return success_response("No changes submitted", {})

    result = users_collection.update_one(
        {"_id": ObjectId(user.get("_id")), "is_active": True},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Profile not found")

    return success_response("Profile updated")
