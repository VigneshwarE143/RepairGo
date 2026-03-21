import logging
from pathlib import Path


class RepairGoLogger:
    """Custom logger wrapper with convenience methods."""
    
    def __init__(self):
        self._logger = logging.getLogger("repairgo")
        self._logger.setLevel(logging.DEBUG)

        log_file = Path(__file__).parent.parent / "repairgo.log"
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
    
    # Delegate standard logging methods
    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)
    
    # Custom convenience methods
    def log_assignment(self, service_id: str, technician_id: str, score: float) -> None:
        self._logger.info(f"Assignment: service={service_id}, technician={technician_id}, score={score:.3f}")

    def log_price_calculation(self, service_id: str, final_price: float, components: dict) -> None:
        self._logger.info(f"Pricing: service={service_id}, final={final_price}, components={components}")

    def log_fraud_flag(self, entity_type: str, entity_id: str, reason: str) -> None:
        self._logger.warning(f"Fraud flag: type={entity_type}, id={entity_id}, reason={reason}")

    def log_admin_action(self, admin_id: str, action: str, details: str) -> None:
        self._logger.info(f"Admin action: admin={admin_id}, action={action}, details={details}")


# Create singleton instance
logger = RepairGoLogger()


# Also export standalone functions for backward compatibility
def log_assignment(service_id: str, technician_id: str, score: float) -> None:
    logger.log_assignment(service_id, technician_id, score)


def log_price_calculation(service_id: str, final_price: float, components: dict) -> None:
    logger.log_price_calculation(service_id, final_price, components)


def log_fraud_flag(entity_type: str, entity_id: str, reason: str) -> None:
    logger.log_fraud_flag(entity_type, entity_id, reason)


def log_admin_action(admin_id: str, action: str, details: str) -> None:
    logger.log_admin_action(admin_id, action, details)
