import math
from typing import Dict, Tuple
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib
import json

from utils.logger import logger


# ============================================================================
# Caching Layer for Performance Optimization
# ============================================================================

class SelectionCache:
    """
    In-memory LRU cache for technician selection computations.
    
    Caches:
    - Distance calculations (static, long TTL)
    - Reliability predictions (dynamic, short TTL)
    
    For production, consider Redis for distributed caching.
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: Dict[str, Tuple[any, datetime]] = {}
        self._max_size = max_size
        self._ttl = timedelta(seconds=ttl_seconds)
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from parameters."""
        key_data = json.dumps(kwargs, sort_keys=True)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Tuple[any, bool]:
        """Get value from cache. Returns (value, hit)."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.utcnow() - timestamp < self._ttl:
                self._hits += 1
                return value, True
            else:
                # Expired
                del self._cache[key]
        
        self._misses += 1
        return None, False
    
    def set(self, key: str, value: any) -> None:
        """Set value in cache."""
        # Evict oldest if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[key] = (value, datetime.utcnow())
    
    def get_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, bool]:
        """Get cached distance calculation."""
        key = self._generate_key("dist", lat1=round(lat1, 4), lon1=round(lon1, 4),
                                  lat2=round(lat2, 4), lon2=round(lon2, 4))
        return self.get(key)
    
    def set_distance(self, lat1: float, lon1: float, lat2: float, lon2: float, distance: float) -> None:
        """Cache distance calculation."""
        key = self._generate_key("dist", lat1=round(lat1, 4), lon1=round(lon1, 4),
                                  lat2=round(lat2, 4), lon2=round(lon2, 4))
        self.set(key, distance)
    
    def get_reliability(self, technician_id: str, service_id: str) -> Tuple[any, bool]:
        """Get cached reliability prediction."""
        key = self._generate_key("rel", tech_id=technician_id, svc_id=service_id)
        return self.get(key)
    
    def set_reliability(self, technician_id: str, service_id: str, prediction: any) -> None:
        """Cache reliability prediction."""
        key = self._generate_key("rel", tech_id=technician_id, svc_id=service_id)
        self.set(key, prediction)
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl.total_seconds(),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }


# Global cache instance
_selection_cache = SelectionCache(max_size=1000, ttl_seconds=300)


def get_cache_stats() -> Dict:
    """Get cache statistics for monitoring."""
    return _selection_cache.get_stats()


def clear_selection_cache() -> None:
    """Clear the selection cache."""
    _selection_cache.clear()


def resolve_technician_coordinates(
	technician: Dict,
	live_max_age_minutes: int = 10,
) -> Tuple[float, float, str]:
	"""
	Choose the best coordinates for a technician.
	- Prefer live coordinates if updated within the recent window.
	- Fall back to home/base coordinates captured at registration.
	- Finally fall back to any stored latitude/longitude or geojson location.
	Returns (lat, lon, source).
	"""
	now = datetime.utcnow()

	last_update = technician.get("last_location_update")
	# Handle string timestamps if they come from Mongo serialization
	if isinstance(last_update, str):
		try:
			last_update = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
		except Exception:
			last_update = None

	live_is_fresh = False
	if last_update:
		live_is_fresh = (now - last_update) <= timedelta(minutes=live_max_age_minutes)

	# Extract live coords
	live_lat = technician.get("latitude")
	live_lon = technician.get("longitude")

	# Fallbacks
	home_lat = technician.get("home_latitude")
	home_lon = technician.get("home_longitude")

	# GeoJSON location fallback
	loc = technician.get("location") or {}
	coords = loc.get("coordinates") if isinstance(loc, dict) else None
	geo_lat = coords[1] if coords and len(coords) >= 2 else None
	geo_lon = coords[0] if coords and len(coords) >= 2 else None

	if live_is_fresh and live_lat is not None and live_lon is not None:
		return float(live_lat), float(live_lon), "live"

	if home_lat is not None and home_lon is not None:
		return float(home_lat), float(home_lon), "home"

	if live_lat is not None and live_lon is not None:
		# Older live coordinate, but still usable as last-known fallback
		return float(live_lat), float(live_lon), "stale"

	if geo_lat is not None and geo_lon is not None:
		return float(geo_lat), float(geo_lon), "geojson"

	# Final fallback
	return 0.0, 0.0, "unknown"


def haversine_distance_km(
	lat1: float,
	lon1: float,
	lat2: float,
	lon2: float,
	use_cache: bool = True,
) -> float:
	"""
	Calculate the great-circle distance between two points on Earth.
	
	Uses caching for repeated calculations.
	"""
	# Check cache first
	if use_cache:
		cached_distance, hit = _selection_cache.get_distance(lat1, lon1, lat2, lon2)
		if hit:
			return cached_distance
	
	radius_km = 6371.0
	lat1_rad = math.radians(lat1)
	lon1_rad = math.radians(lon1)
	lat2_rad = math.radians(lat2)
	lon2_rad = math.radians(lon2)

	delta_lat = lat2_rad - lat1_rad
	delta_lon = lon2_rad - lon1_rad

	a = (
		math.sin(delta_lat / 2) ** 2
		+ math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
	)
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	distance = radius_km * c
	
	# Cache the result
	if use_cache:
		_selection_cache.set_distance(lat1, lon1, lat2, lon2, distance)
	
	return distance


def get_predicted_success_probability(
	service: Dict,
	technician: Dict,
	distance_km: float,
	avg_response_time: float = 30.0,
	use_cache: bool = True,
) -> Tuple[float, str]:
	"""
	Get the predicted success probability for a technician-service pair.
	
	Uses ML model if available, otherwise falls back to rule-based scoring.
	Results are cached for performance.
	
	Returns:
		Tuple of (probability, source) where source is "model" or "fallback"
	"""
	tech_id = str(technician.get("_id", ""))
	service_id = str(service.get("_id", ""))
	
	# Check cache first
	if use_cache and tech_id and service_id:
		cached_result, hit = _selection_cache.get_reliability(tech_id, service_id)
		if hit:
			return cached_result
	
	try:
		from ml.predictor import predict_reliability, is_model_available
		
		# Extract technician stats
		completed = int(technician.get("completed_jobs", 0) or 0)
		cancelled = int(technician.get("cancelled_jobs", 0) or 0)
		total_jobs = max(completed + cancelled, 1)
		
		avg_rating = float(technician.get("rating", 0.0) or 0.0)
		cancellation_rate = cancelled / total_jobs
		current_workload = int(technician.get("workload", 0) or 0)
		
		result = predict_reliability(
			avg_rating=avg_rating,
			cancellation_rate=cancellation_rate,
			avg_response_time=avg_response_time,
			completed_jobs=completed,
			current_workload=current_workload,
			distance_to_customer=distance_km,
			include_explainability=False,  # Skip for selection speed
		)
		
		prediction = (result["success_probability"], result["prediction_source"])
		
		# Cache the result
		if use_cache and tech_id and service_id:
			_selection_cache.set_reliability(tech_id, service_id, prediction)
		
		return prediction
		
	except ImportError:
		# ML module not available, use fallback
		logger.warning("ML module not available, using fallback scoring")
		prediction = (calculate_fallback_success_probability(technician, distance_km), "fallback")
		return prediction
	except Exception as e:
		logger.error(f"Error getting prediction, using fallback: {e}")
		prediction = (calculate_fallback_success_probability(technician, distance_km), "fallback")
		return prediction


def calculate_fallback_success_probability(
	technician: Dict,
	distance_km: float,
	max_distance_km: float = 50.0,
	max_workload: int = 10,
) -> float:
	"""
	Calculate success probability using rule-based fallback logic.
	
	This is used when the ML model is unavailable.
	"""
	completed = int(technician.get("completed_jobs", 0) or 0)
	cancelled = int(technician.get("cancelled_jobs", 0) or 0)
	total_jobs = max(completed + cancelled, 1)
	
	avg_rating = float(technician.get("rating", 0.0) or 0.0)
	cancellation_rate = cancelled / total_jobs
	current_workload = int(technician.get("workload", 0) or 0)
	
	# Normalize each feature
	rating_score = max(0.0, min(1.0, avg_rating / 5.0))
	cancel_score = max(0.0, 1.0 - (cancellation_rate * 2))
	experience_score = min(1.0, completed / 100.0)
	workload_score = max(0.0, 1.0 - (current_workload / max_workload))
	distance_score = max(0.0, 1.0 - (distance_km / max_distance_km))
	
	# Weighted combination
	probability = (
		0.35 * rating_score +
		0.30 * cancel_score +
		0.15 * experience_score +
		0.10 * workload_score +
		0.10 * distance_score
	)
	
	return max(0.0, min(1.0, probability))


def calculate_score(
	service: Dict,
	technician: Dict,
	max_distance_km: float = 50.0,
	max_workload: int = 10,
	use_ml_prediction: bool = True,
) -> Tuple[float, Dict[str, float]]:
	"""
	Calculate technician score for a service request.
	
	Updated Formula (ETA-PRIORITIZED for fastest technician selection):
	Score = (0.20 × SkillMatch) + (0.35 × ProximityScore) + (0.15 × Availability) +
			(0.20 × PredictedSuccessProbability) + (0.10 × WorkloadScore)
	
	ProximityScore is heavily weighted to ensure fastest arrival time.
	If ML model unavailable, falls back to rule-based predicted probability.
	"""
	category = service.get("category", "")
	skills = technician.get("skills", []) or []
	skill_match = 1.0 if category in skills else 0.0

	service_location = service.get("location", {}) or {}
	service_lat = service_location.get("latitude", 0.0)
	service_lon = service_location.get("longitude", 0.0)
	tech_lat, tech_lon, coord_source = resolve_technician_coordinates(technician)

	distance_km = haversine_distance_km(
		service_lat,
		service_lon,
		tech_lat,
		tech_lon,
	)
	# Use inverse exponential for proximity to heavily favor closer technicians
	# A technician 5km away gets ~0.9, 10km gets ~0.82, 25km gets ~0.61, 50km gets ~0.37
	proximity_score = max(0.0, 1.0 - (distance_km / max_distance_km))
	# Apply exponential boost for very close technicians (ETA priority)
	proximity_score = proximity_score ** 0.7  # Makes close distances score even higher

	availability_score = 1.0 if technician.get("availability", False) else 0.0

	workload = int(technician.get("workload", 0) or 0)
	workload_score = max(0.0, 1.0 - (workload / max_workload))

	# Get predicted success probability (ML or fallback)
	if use_ml_prediction:
		predicted_success, prediction_source = get_predicted_success_probability(
			service=service,
			technician=technician,
			distance_km=distance_km,
		)
	else:
		# Fallback to original rating-based score for testing
		rating = float(technician.get("rating", 0.0) or 0.0)
		predicted_success = max(0.0, min(1.0, rating / 5.0))
		prediction_source = "legacy"

	# New scoring formula with ML prediction (ETA-PRIORITIZED)
	# Score = (0.20 × SkillMatch) + (0.35 × Proximity) + (0.15 × Availability) +
	#         (0.20 × PredictedSuccessProbability) + (0.10 × WorkloadScore)
	score = (
		0.20 * skill_match
		+ 0.35 * proximity_score
		+ 0.15 * availability_score
		+ 0.20 * predicted_success
		+ 0.10 * workload_score
	)

	components = {
		"skill_match": skill_match,
		"proximity_score": proximity_score,
		"availability": availability_score,
		"predicted_success_probability": predicted_success,
		"prediction_source": prediction_source,
		"workload_score": workload_score,
		"distance_km": distance_km,
		"coordinate_source": coord_source,
	}
	return score, components


def estimate_eta_minutes(distance_km: float, average_speed_kmh: float = 40.0) -> float:
	if average_speed_kmh <= 0:
		return 0.0
	return (distance_km / average_speed_kmh) * 60.0


def select_best_technician(
	service: Dict,
	technicians: list,
	exclude_ids: set | None = None,
) -> Tuple[Dict | None, float, Dict[str, float]]:
	exclude_ids = exclude_ids or set()
	best = None
	best_score = -1.0
	best_components: Dict[str, float] = {}

	for technician in technicians:
		tech_id = str(technician.get("_id"))
		if tech_id in exclude_ids:
			continue
		score, components = calculate_score(service, technician)
		if score > best_score:
			best = technician
			best_score = score
			best_components = components

	return best, best_score, best_components
