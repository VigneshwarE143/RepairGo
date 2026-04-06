import base64
from io import BytesIO

import qrcode


def validate_upi_id(upi_id: str) -> str:
    if upi_id is None:
        raise ValueError("UPI ID is required")
    normalized = upi_id.strip()
    if not normalized:
        raise ValueError("UPI ID cannot be empty")
    if "@" not in normalized:
        raise ValueError("UPI ID must contain '@'")
    return normalized


def generate_upi_qr(upi_id: str, name: str, amount: float) -> str:
    safe_upi = validate_upi_id(upi_id)
    safe_name = (name or "Technician").strip()
    safe_amount = round(float(amount), 2)
    upi_url = f"upi://pay?pa={safe_upi}&pn={safe_name}&am={safe_amount}&cu=INR"

    qr = qrcode.make(upi_url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()
