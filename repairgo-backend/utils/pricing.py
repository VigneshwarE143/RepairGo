from typing import Dict, Optional

from utils.technician_selection import haversine_distance_km
from utils.logger import logger
from database import categories_collection

BASE_PRICES: Dict[str, float] = {
	"plumbing": 60.0,
	"electrical": 70.0,
	"hvac": 90.0,
	"appliance": 65.0,
	"general": 50.0,
}

TRAVEL_RATE_PER_KM = 2.0

URGENCY_ADDON = {
	"low": 0.0,
	"medium": 10.0,
	"high": 25.0,
}

# Fallback thresholds (used when ML prediction unavailable)
LOW_DEMAND_THRESHOLD = 5
HIGH_DEMAND_THRESHOLD = 15


def demand_multiplier_static(active_requests: int) -> float:
	"""
	Static demand multiplier based on current active requests.
	
	This is the fallback method when ML prediction is unavailable.
	"""
	if active_requests > HIGH_DEMAND_THRESHOLD:
		return 1.2
	if active_requests < LOW_DEMAND_THRESHOLD:
		return 0.9
	return 1.0


def demand_multiplier_ml() -> Dict:
	"""
	Get demand multiplier using ML-based prediction.
	
	Returns:
		Dictionary with multiplier and prediction details
	"""
	try:
		from ml.demand_predictor import predict_demand
		
		result = predict_demand(use_cache=True)
		return {
			"multiplier": result["multiplier"],
			"demand_level": result["demand_level"],
			"predicted_count": result["predicted_count"],
			"prediction_source": result["prediction_source"],
			"from_cache": result.get("from_cache", False),
		}
	except ImportError:
		logger.warning("ML demand predictor not available, using static multiplier")
		return None
	except Exception as e:
		logger.warning(f"ML demand prediction failed: {e}")
		return None


def get_demand_multiplier(active_requests: int, use_ml: bool = True) -> Dict:
	"""
	Get the demand multiplier for pricing.
	
	Uses ML-based prediction if available, otherwise falls back to static method.
	
	Args:
		active_requests: Current number of active service requests
		use_ml: Whether to attempt ML-based prediction (default: True)
	
	Returns:
		Dictionary with multiplier and details:
		- multiplier: float (0.9, 1.0, or 1.2)
		- demand_level: "low", "normal", or "high"
		- prediction_source: "ml_model", "ml_fallback", or "static"
	"""
	if use_ml:
		ml_result = demand_multiplier_ml()
		if ml_result:
			return ml_result
	
	# Fallback to static method
	multiplier = demand_multiplier_static(active_requests)
	
	if active_requests > HIGH_DEMAND_THRESHOLD:
		demand_level = "high"
	elif active_requests < LOW_DEMAND_THRESHOLD:
		demand_level = "low"
	else:
		demand_level = "normal"
	
	return {
		"multiplier": multiplier,
		"demand_level": demand_level,
		"predicted_count": active_requests,
		"prediction_source": "static",
		"from_cache": False,
	}


def estimate_distance_km(service_location: Dict, technicians: list) -> float:
	if not technicians:
		return 0.0

	distances = []
	for tech in technicians:
		distances.append(
			haversine_distance_km(
				service_location.get("latitude", 0.0),
				service_location.get("longitude", 0.0),
				tech.get("latitude", 0.0),
				tech.get("longitude", 0.0),
			)
		)

	return min(distances) if distances else 0.0


def estimate_price(
	category: str,
	urgency: str,
	distance_km: float,
	active_requests: int,
	use_ml_demand: bool = True,
) -> Dict:
	"""
	Estimate the price for a service request.
	
	Uses ML-based demand prediction for the surge multiplier if available.
	
	Args:
		category: Service category
		urgency: Urgency level ("low", "medium", "high")
		distance_km: Distance to nearest technician
		active_requests: Current number of active requests (fallback)
		use_ml_demand: Whether to use ML demand prediction (default: True)
	
	Returns:
		Dictionary with price breakdown and demand info
	"""
	base_price = BASE_PRICES.get(category, BASE_PRICES["general"])
	category_doc = categories_collection.find_one({"name": category})
	if category_doc and isinstance(category_doc.get("base_price"), (int, float)):
		base_price = float(category_doc.get("base_price"))
	
	travel_cost = distance_km * TRAVEL_RATE_PER_KM
	urgency_addon = URGENCY_ADDON.get(urgency, 0.0)
	
	# Get demand multiplier (ML or static)
	demand_info = get_demand_multiplier(active_requests, use_ml=use_ml_demand)
	surge_multiplier = demand_info["multiplier"]
	
	subtotal = base_price + travel_cost + urgency_addon
	final_price = subtotal * surge_multiplier

	return {
		"base_price": base_price,
		"travel_cost": travel_cost,
		"urgency_addon": urgency_addon,
		"demand_multiplier": surge_multiplier,
		"demand_level": demand_info["demand_level"],
		"demand_prediction_source": demand_info["prediction_source"],
		"predicted_demand_count": demand_info["predicted_count"],
		"distance_km": distance_km,
		"final_price": final_price,
	}


# Backward compatibility alias
def demand_multiplier(active_requests: int) -> float:
	"""
	Legacy function for backward compatibility.
	
	Prefer using get_demand_multiplier() for new code.
	"""
	result = get_demand_multiplier(active_requests, use_ml=True)
	return result["multiplier"]

