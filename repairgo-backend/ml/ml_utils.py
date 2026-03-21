"""
ML Utilities - Safeguards for ML Integration.

Provides:
- Timeout guards for ML operations
- Latency logging
- Graceful fallback handling
"""

import time
import functools
import threading
from typing import Any, Callable, Dict, Optional, TypeVar, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from utils.logger import logger

# Default timeout for ML operations (in seconds)
DEFAULT_ML_TIMEOUT = 5.0

# Type variable for generic return types
T = TypeVar('T')


class MLTimeoutError(Exception):
    """Exception raised when an ML operation times out."""
    pass


class MLPredictionResult:
    """
    Container for ML prediction results with metadata.
    """
    def __init__(
        self,
        result: Any,
        latency_ms: float,
        source: str,
        timed_out: bool = False,
        error: Optional[str] = None,
    ):
        self.result = result
        self.latency_ms = latency_ms
        self.source = source
        self.timed_out = timed_out
        self.error = error
    
    def to_dict(self) -> Dict:
        return {
            "result": self.result,
            "latency_ms": round(self.latency_ms, 3),
            "source": self.source,
            "timed_out": self.timed_out,
            "error": self.error,
        }


def timed_execution(
    func: Callable[..., T],
    *args,
    timeout: float = DEFAULT_ML_TIMEOUT,
    fallback: Optional[Callable[..., T]] = None,
    operation_name: str = "ML operation",
    **kwargs,
) -> Tuple[T, float, str]:
    """
    Execute a function with timeout and latency tracking.
    
    Args:
        func: The function to execute
        *args: Positional arguments to pass to func
        timeout: Timeout in seconds (default: 5.0)
        fallback: Optional fallback function if main func fails/times out
        operation_name: Name for logging purposes
        **kwargs: Keyword arguments to pass to func
    
    Returns:
        Tuple of (result, latency_ms, source) where source is
        "model", "fallback", or "error"
    """
    start_time = time.perf_counter()
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout)
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                logger.debug(
                    f"[{operation_name}] completed in {latency_ms:.2f}ms (model)"
                )
                
                return result, latency_ms, "model"
                
            except FuturesTimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"[{operation_name}] timed out after {timeout}s "
                    f"({latency_ms:.2f}ms)"
                )
                
                if fallback is not None:
                    fb_start = time.perf_counter()
                    fb_result = fallback(*args, **kwargs)
                    fb_latency = (time.perf_counter() - fb_start) * 1000
                    total_latency = (time.perf_counter() - start_time) * 1000
                    
                    logger.info(
                        f"[{operation_name}] fallback completed in {fb_latency:.2f}ms "
                        f"(total: {total_latency:.2f}ms)"
                    )
                    
                    return fb_result, total_latency, "fallback_timeout"
                
                raise MLTimeoutError(f"{operation_name} timed out after {timeout}s")
                
    except MLTimeoutError:
        raise
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"[{operation_name}] failed in {latency_ms:.2f}ms: {str(e)}"
        )
        
        if fallback is not None:
            fb_start = time.perf_counter()
            try:
                fb_result = fallback(*args, **kwargs)
                fb_latency = (time.perf_counter() - fb_start) * 1000
                total_latency = (time.perf_counter() - start_time) * 1000
                
                logger.info(
                    f"[{operation_name}] fallback completed in {fb_latency:.2f}ms "
                    f"(total: {total_latency:.2f}ms)"
                )
                
                return fb_result, total_latency, "fallback_error"
            except Exception as fb_error:
                logger.error(f"[{operation_name}] fallback also failed: {fb_error}")
                raise
        
        raise


def with_latency_logging(operation_name: str):
    """
    Decorator to add latency logging to any function.
    
    Usage:
        @with_latency_logging("Reliability prediction")
        def predict_reliability(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                # Add latency to result if it's a dict
                if isinstance(result, dict):
                    result["latency_ms"] = round(latency_ms, 3)
                
                logger.debug(f"[{operation_name}] completed in {latency_ms:.2f}ms")
                return result
                
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"[{operation_name}] failed in {latency_ms:.2f}ms: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator


def with_timeout(timeout: float = DEFAULT_ML_TIMEOUT, operation_name: str = "ML"):
    """
    Decorator to add timeout to any function.
    
    Usage:
        @with_timeout(timeout=3.0, operation_name="Fraud detection")
        def detect_fraud(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout)
                except FuturesTimeoutError:
                    logger.error(
                        f"[{operation_name}] timed out after {timeout}s"
                    )
                    raise MLTimeoutError(
                        f"{operation_name} timed out after {timeout}s"
                    )
        return wrapper
    return decorator


def safe_ml_call(
    ml_func: Callable[..., T],
    fallback_func: Callable[..., T],
    *args,
    timeout: float = DEFAULT_ML_TIMEOUT,
    operation_name: str = "ML prediction",
    **kwargs,
) -> Dict:
    """
    Safely call an ML function with timeout, fallback, and latency logging.
    
    This is the main utility for ML integration points.
    
    Args:
        ml_func: The ML prediction function
        fallback_func: Fallback function if ML fails
        *args: Arguments for both functions
        timeout: Timeout in seconds
        operation_name: Name for logging
        **kwargs: Keyword arguments for both functions
    
    Returns:
        Dictionary with:
        - result: The prediction result
        - latency_ms: Total latency in milliseconds
        - source: "model", "fallback_timeout", "fallback_error", or "fallback"
        - model_available: Whether ML model was attempted
    """
    start_time = time.perf_counter()
    source = "model"
    model_available = True
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ml_func, *args, **kwargs)
            try:
                result = future.result(timeout=timeout)
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                logger.debug(
                    f"[{operation_name}] ML completed in {latency_ms:.2f}ms"
                )
                
                return {
                    "result": result,
                    "latency_ms": round(latency_ms, 3),
                    "source": source,
                    "model_available": model_available,
                }
                
            except FuturesTimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"[{operation_name}] ML timed out after {timeout}s"
                )
                source = "fallback_timeout"
                
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            f"[{operation_name}] ML failed in {latency_ms:.2f}ms: {e}"
        )
        source = "fallback_error"
        model_available = False
    
    # Execute fallback
    fb_start = time.perf_counter()
    try:
        result = fallback_func(*args, **kwargs)
        total_latency = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"[{operation_name}] fallback completed, total: {total_latency:.2f}ms"
        )
        
        return {
            "result": result,
            "latency_ms": round(total_latency, 3),
            "source": source,
            "model_available": model_available,
        }
        
    except Exception as e:
        total_latency = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"[{operation_name}] fallback also failed: {e}"
        )
        
        # Return a safe default
        return {
            "result": None,
            "latency_ms": round(total_latency, 3),
            "source": "error",
            "error": str(e),
            "model_available": model_available,
        }
