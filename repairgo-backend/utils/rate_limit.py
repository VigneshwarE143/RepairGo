from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple

rate_limit_store: Dict[str, list] = defaultdict(list)
RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 300


def is_rate_limited(client_ip: str) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)

    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []

    rate_limit_store[client_ip] = [
        attempt for attempt in rate_limit_store[client_ip]
        if attempt > cutoff
    ]

    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_ATTEMPTS:
        return True

    rate_limit_store[client_ip].append(now)
    return False


def reset_rate_limit(client_ip: str) -> None:
    if client_ip in rate_limit_store:
        rate_limit_store[client_ip] = []
