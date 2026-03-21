"""Background job monitoring and health tracking."""

from datetime import datetime
from typing import Dict, Any
from enum import Enum


class JobStatus(str, Enum):
    """Status of background job execution."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundJobMonitor:
    """Monitors and tracks background job execution metrics."""
    
    def __init__(self):
        self.job_name = "reassignment_stale_jobs"
        self.status = JobStatus.IDLE
        self.last_execution: datetime = None
        self.next_execution: datetime = None
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_error: str = None
        self.metrics: Dict[str, Any] = {
            "reassigned": 0,
            "attempted": 0,
            "execution_time_ms": 0,
        }
    
    def start_execution(self) -> None:
        """Mark job as started."""
        self.status = JobStatus.RUNNING
        self.last_execution = datetime.utcnow()
    
    def complete_execution(self, metrics: Dict[str, Any]) -> None:
        """Mark job as completed successfully."""
        self.status = JobStatus.COMPLETED
        self.execution_count += 1
        self.success_count += 1
        self.metrics = metrics
        self.last_error = None
    
    def fail_execution(self, error: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.execution_count += 1
        self.failure_count += 1
        self.last_error = error
    
    def set_next_execution(self, next_run: datetime) -> None:
        """Set the next scheduled execution time."""
        self.next_execution = next_run
    
    def get_status(self) -> Dict[str, Any]:
        """Get current job status and metrics."""
        return {
            "job_name": self.job_name,
            "status": self.status.value,
            "last_execution": self.last_execution,
            "next_execution": self.next_execution,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "metrics": self.metrics,
            "health": "healthy" if self.failure_count == 0 else "degraded",
        }


# Global monitor instance
job_monitor = BackgroundJobMonitor()
