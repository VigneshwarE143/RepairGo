import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { serviceAPI, technicianAPI } from "../../services/api";
import MapView from "../../components/MapView";

const STATUS_FLOW = {
  accepted: {
    next: "on_the_way",
    label: "Start Navigation",
    icon: "🚗",
    action: "startNavigation",
  },
  on_the_way: {
    next: "in_progress",
    label: "I've Arrived",
    icon: "📍",
    action: "arrive",
  },
  in_progress: {
    next: "completed",
    label: "Complete Job",
    icon: "✅",
    action: "complete",
  },
  // Legacy support for assigned status
  assigned: {
    next: "on_the_way",
    label: "Start Navigation",
    icon: "🚗",
    action: "startNavigation",
  },
};

export default function JobDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [isUpdatingLocation, setIsUpdatingLocation] = useState(false);
  const [locationWatchId, setLocationWatchId] = useState(null);
  const [myLocation, setMyLocation] = useState(null);

  useEffect(() => {
    loadJob();
  }, [id]);

  // WebSocket remains primary; polling provides fallback reliability.
  useEffect(() => {
    const isTerminal =
      job?.status === "cancelled" ||
      job?.status === "rated" ||
      (job?.status === "completed" && job?.payment_status === "paid");
    if (isTerminal) return;

    const interval = setInterval(async () => {
      try {
        const pendingResponse = await technicianAPI.getPendingJobs();
        const pendingJob = pendingResponse.data?.find((j) => j._id === id);
        if (pendingJob) {
          setJob((prev) => ({ ...prev, ...pendingJob }));
          return;
        }

        // If no longer pending, refresh from full job list to reflect assignment/progress updates.
        const jobsResponse = await technicianAPI.getMyJobs();
        const currentJob = jobsResponse.data?.find((j) => j._id === id);
        if (currentJob) {
          setJob((prev) => ({ ...prev, ...currentJob }));
        }
      } catch {
        // Ignore polling failures; websocket/next poll will resync.
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [id, job?.status]);

  // Get initial location for the map
  useEffect(() => {
    if (navigator.geolocation && !myLocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setMyLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            heading: position.coords.heading,
            speed_kmh: position.coords.speed
              ? position.coords.speed * 3.6
              : null,
          });
        },
        () => {},
        { enableHighAccuracy: true },
      );
    }
  }, []);

  // Auto-update location when accepted or on_the_way so customer can track immediately after acceptance
  useEffect(() => {
    if (
      ["accepted", "on_the_way"].includes(job?.status) &&
      navigator.geolocation
    ) {
      const watchId = navigator.geolocation.watchPosition(
        (position) => {
          updateLiveLocation(position);
        },
        () => {
          // Location tracking unavailable
        },
        { enableHighAccuracy: true, maximumAge: 5000 },
      );
      setLocationWatchId(watchId);
      return () => {
        if (watchId) navigator.geolocation.clearWatch(watchId);
      };
    }
    return () => {
      if (locationWatchId) navigator.geolocation.clearWatch(locationWatchId);
    };
  }, [job?.status]);

  const updateLiveLocation = async (position) => {
    // Store my current location in state for the map
    setMyLocation({
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      heading: position.coords.heading,
      speed_kmh: position.coords.speed ? position.coords.speed * 3.6 : null,
    });

    if (isUpdatingLocation) return;
    setIsUpdatingLocation(true);
    try {
      await technicianAPI.updateLiveLocation({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        heading: position.coords.heading || null,
        speed_kmh: position.coords.speed ? position.coords.speed * 3.6 : null, // m/s to km/h
        accuracy_meters: position.coords.accuracy,
        is_navigating: job?.status === "on_the_way",
        active_job_id: id,
      });
    } catch (error) {
      // Silently fail - location updates are best effort
    } finally {
      setIsUpdatingLocation(false);
    }
  };

  const loadJob = async () => {
    setLoading(true);
    try {
      const response = await technicianAPI.getMyJobs();
      const found = response.data?.find((j) => j._id === id);
      if (found) {
        setJob(found);
      } else {
        toast.error("Job not found");
        navigate("/technician/jobs");
      }
    } catch (error) {
      toast.error("Failed to load job");
    } finally {
      setLoading(false);
    }
  };

  const handleStatusAction = async () => {
    const statusInfo = STATUS_FLOW[job.status];
    if (!statusInfo) return;

    setProcessing(true);
    try {
      // Use the new navigation endpoints
      if (statusInfo.action === "startNavigation") {
        await technicianAPI.startNavigation(id);
        toast.success(
          "Navigation started! Customer can now track your location.",
        );
      } else if (statusInfo.action === "arrive") {
        await technicianAPI.arrive(id);
        toast.success("Marked as arrived. You can now start working.");
      } else if (statusInfo.action === "complete") {
        await technicianAPI.complete(id);
        toast.success("Job completed! Great work!");
      }
      loadJob();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update status");
    } finally {
      setProcessing(false);
    }
  };

  const updateStatus = async () => {
    const statusInfo = STATUS_FLOW[job.status];
    if (!statusInfo) return;

    setProcessing(true);
    try {
      await serviceAPI.updateStatus(id, { status: statusInfo.next });
      toast.success(`Status updated to ${statusInfo.next.replace(/_/g, " ")}`);
      loadJob();
    } catch (error) {
      toast.error(error.message || "Failed to update status");
    } finally {
      setProcessing(false);
    }
  };

  const cancelJob = async () => {
    setProcessing(true);
    try {
      // Technicians reject/cancel jobs through the respond endpoint
      await technicianAPI.respondToJob(id, {
        action: "reject",
        reject_reason: "Cancelled by technician from job details page",
      });
      toast.success("Job rejected - customer will be reassigned");
      setShowCancelModal(false);
      navigate("/technician/jobs");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to reject job");
    } finally {
      setProcessing(false);
    }
  };

  const confirmPaymentReceived = async () => {
    setProcessing(true);
    try {
      await technicianAPI.confirmPayment(id, { technician_confirmed: true });
      toast.success("Payment confirmed and marked as paid");
      loadJob();
    } catch (error) {
      toast.error(error.message || "Failed to confirm payment");
    } finally {
      setProcessing(false);
    }
  };

  const getPaymentStatusLabel = (status) => {
    if (status === "paid") return "Paid";
    if (status === "pending_confirmation") return "Waiting for Confirmation";
    return "Pending";
  };

  const getStatusBadge = (status) => {
    const classes = {
      awaiting_technician_acceptance: "badge-warning",
      accepted: "badge-info",
      assigned: "badge-assigned",
      on_the_way: "badge-info",
      in_progress: "badge-in-progress",
      completed: "badge-completed",
      rated: "badge-secondary",
      cancelled: "badge-cancelled",
    };
    return (
      <span
        className={`badge ${classes[status] || "badge-secondary"}`}
        style={{ fontSize: "0.875rem", padding: "6px 12px" }}
      >
        {status?.replace(/_/g, " ")}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="loading-page">
        <div className="loading-spinner lg"></div>
      </div>
    );
  }

  if (!job) return null;

  const statusInfo = STATUS_FLOW[job.status];
  const canAdvance = !!statusInfo;
  const canCancel = [
    "assigned",
    "accepted",
    "on_the_way",
    "in_progress",
  ].includes(job.status);

  return (
    <div>
      <div className="page-header">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            marginBottom: "8px",
          }}
        >
          <button className="btn btn-ghost" onClick={() => navigate(-1)}>
            ← Back
          </button>
        </div>
        <h1>Job</h1>
        <p className="text-muted text-sm">#{job._id}</p>
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px" }}
      >
        {/* Main Content */}
        <div>
          {/* Status Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Status</h3>
              {getStatusBadge(job.status)}
            </div>
            <div className="card-body">
              {canAdvance && (
                <div
                  className="alert alert-info"
                  style={{ marginBottom: "16px" }}
                >
                  <span className="alert-icon">{statusInfo.icon}</span>
                  <div className="alert-content">
                    <strong>{statusInfo.label}</strong>
                  </div>
                </div>
              )}

              <div style={{ display: "flex", gap: "12px" }}>
                {canAdvance && (
                  <button
                    className="btn btn-primary btn-lg"
                    onClick={handleStatusAction}
                    disabled={processing}
                    style={{ flex: 1 }}
                  >
                    {processing ? (
                      <>
                        <span className="loading-spinner sm"></span>
                        Updating
                      </>
                    ) : (
                      <>
                        {statusInfo.icon} {statusInfo.label}
                      </>
                    )}
                  </button>
                )}

                {canCancel && (
                  <button
                    className="btn btn-danger"
                    onClick={() => setShowCancelModal(true)}
                  >
                    Cancel
                  </button>
                )}
              </div>

              {/* Live Location Tracking Status */}
              {job.status === "on_the_way" && (
                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px 16px",
                    background: "var(--success-bg)",
                    borderRadius: "8px",
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                  }}
                >
                  <span
                    style={{
                      animation: "pulse 1s infinite",
                      fontSize: "1.2rem",
                    }}
                  >
                    📍
                  </span>
                  <div>
                    <strong style={{ color: "var(--success)" }}>Live</strong>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Job Details */}
          <div className="card" style={{ marginTop: "24px" }}>
            <div className="card-header">
              <h3 className="card-title">Details</h3>
            </div>
            <div className="card-body">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                  gap: "16px",
                }}
              >
                <div>
                  <div className="text-secondary text-xs">Category</div>
                  <div
                    className="font-semibold"
                    style={{ textTransform: "capitalize" }}
                  >
                    {job.category}
                  </div>
                </div>
                <div>
                  <div className="text-secondary text-xs">Urgency</div>
                  <span
                    className={`badge ${job.urgency === "high" ? "badge-danger" : job.urgency === "medium" ? "badge-warning" : "badge-secondary"}`}
                  >
                    {job.urgency}
                  </span>
                </div>
                <div>
                  <div className="text-secondary text-xs">Created</div>
                  <div className="font-semibold">
                    {new Date(job.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
              {job.description && (
                <details style={{ marginTop: "16px" }}>
                  <summary className="text-secondary text-sm">Notes</summary>
                  <p style={{ marginTop: "8px" }}>{job.description}</p>
                </details>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div>
          {/* Live Navigation Map */}
          {(job.status === "on_the_way" ||
            job.status === "accepted" ||
            job.status === "assigned") && (
            <div className="card" style={{ marginBottom: "16px" }}>
              <div className="card-header">
                <h3 className="card-title">Map</h3>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <MapView
                  selfPosition={
                    myLocation?.latitude && myLocation?.longitude
                      ? [myLocation.latitude, myLocation.longitude]
                      : null
                  }
                  technicianPosition={
                    myLocation?.latitude && myLocation?.longitude
                      ? [myLocation.latitude, myLocation.longitude]
                      : null
                  }
                  customerPosition={
                    job.location?.latitude && job.location?.longitude
                      ? [job.location.latitude, job.location.longitude]
                      : null
                  }
                  technicianName="You"
                  customerAddress="Customer Location"
                  eta={job.live_eta_minutes || job.eta_minutes}
                  distance={job.technician_distance_km}
                  speed={myLocation?.speed_kmh}
                  heading={myLocation?.heading}
                  status={job.status}
                  mode="technician"
                  height="300px"
                />
              </div>
            </div>
          )}

          {/* Customer Location */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Location</h3>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gap: "12px" }}>
                {(job.live_eta_minutes || job.eta_minutes) && (
                  <div>
                    <span className="text-secondary text-sm">ETA</span>
                    <p className="font-semibold">
                      {job.live_eta_minutes || job.eta_minutes}m
                    </p>
                  </div>
                )}
                {job.technician_distance_km && (
                  <div>
                    <span className="text-secondary text-sm">Distance</span>
                    <p className="font-semibold">
                      {job.technician_distance_km.toFixed(1)} km
                    </p>
                  </div>
                )}
              </div>
              <button
                className="btn btn-outline btn-block mt-4"
                onClick={() => {
                  const lat = job.location?.latitude;
                  const lng = job.location?.longitude;
                  if (lat && lng) {
                    window.open(
                      `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`,
                      "_blank",
                    );
                  }
                }}
              >
                Open in Maps
              </button>
            </div>
          </div>

          {/* Payment Info */}
          <div className="card" style={{ marginTop: "16px" }}>
            <div className="card-header">
              <h3 className="card-title">Payment</h3>
            </div>
            <div className="card-body">
              <div style={{ textAlign: "center" }}>
                <div className="text-secondary text-sm">Estimate</div>
                <div
                  style={{
                    fontSize: "2rem",
                    fontWeight: 700,
                    color: "var(--primary)",
                  }}
                >
                  ₹{job.estimated_price?.toFixed(2) || "0.00"}
                </div>
                {job.payment_status && (
                  <span
                    className={`badge ${job.payment_status === "paid" ? "badge-success" : job.payment_status === "pending_confirmation" ? "badge-info" : "badge-warning"} mt-2`}
                  >
                    {getPaymentStatusLabel(job.payment_status)}
                  </span>
                )}

                {job.customer_paid &&
                  !job.technician_confirmed &&
                  job.payment_method === "upi" && (
                    <div style={{ marginTop: "12px" }}>
                      <div
                        className="text-secondary text-sm"
                        style={{ marginBottom: "8px" }}
                      >
                        Customer paid
                      </div>
                      <button
                        className="btn btn-primary btn-block"
                        onClick={confirmPaymentReceived}
                        disabled={processing}
                      >
                        {processing ? "..." : "Confirm"}
                      </button>
                    </div>
                  )}
              </div>
            </div>
          </div>

          {/* Rating */}
          {job.rating && (
            <div className="card" style={{ marginTop: "16px" }}>
              <div className="card-header">
                <h3 className="card-title">⭐ Rating</h3>
              </div>
              <div className="card-body" style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2rem" }}>
                  {"⭐".repeat(job.rating)}
                </div>
                <p className="text-secondary">{job.rating}/5 stars</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowCancelModal(false)}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Cancel</h3>
              <button
                className="modal-close"
                onClick={() => setShowCancelModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <p>Cancel this job?</p>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCancelModal(false)}
              >
                Keep
              </button>
              <button
                className="btn btn-danger"
                onClick={cancelJob}
                disabled={processing}
              >
                {processing ? "..." : "Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
