from typing import Dict

TECH_CANCEL_THRESHOLD = 3
PRICE_DEVIATION_THRESHOLD = 0.3


def flag_technician_if_needed(technician: Dict) -> bool:
    cancelled_jobs = int(technician.get("cancelled_jobs", 0) or 0)
    return cancelled_jobs > TECH_CANCEL_THRESHOLD


def flag_service_if_price_deviation(service: Dict) -> bool:
    estimated = service.get("estimated_price")
    final = service.get("final_price")
    if not isinstance(estimated, (int, float)) or not isinstance(final, (int, float)):
        return False
    if estimated <= 0:
        return False
    deviation = abs(final - estimated) / estimated
    return deviation > PRICE_DEVIATION_THRESHOLD
