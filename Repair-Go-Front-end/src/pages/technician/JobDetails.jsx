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
        <h1>Job Details</h1>
        <p>Job ID: {job._id}</p>
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px" }}
      >
        {/* Main Content */}
        <div>
          {/* Status Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Job Status</h3>
              {getStatusBadge(job.status)}
            </div>
            <div className="card-body">
              {/* Progress */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "24px",
                }}
              >
                {["accepted", "on_the_way", "in_progress", "completed"].map(
                  (status, index) => {
                    const steps = [
                      "accepted",
                      "on_the_way",
                      "in_progress",
                      "completed",
                    ];
                    // Also support legacy "assigned" status
                    const jobStatusForComparison =
                      job.status === "assigned" ? "accepted" : job.status;
                    const currentIndex = steps.indexOf(jobStatusForComparison);
                    const isActive = index <= currentIndex;
                    const isCurrent = status === jobStatusForComparison;

                    return (
                      <div
                        key={status}
                        style={{ textAlign: "center", flex: 1 }}
                      >
                        <div
                          style={{
                            width: 40,
                            height: 40,
                            borderRadius: "50%",
                            background: isActive
                              ? "var(--primary)"
                              : "var(--gray-200)",
                            color: isActive ? "white" : "var(--gray-500)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            margin: "0 auto 8px",
                            fontWeight: 600,
                            border: isCurrent
                              ? "3px solid var(--primary-dark)"
                              : "none",
                          }}
                        >
                          {index < currentIndex ? "✓" : index + 1}
                        </div>
                        <span
                          className={`text-sm ${isActive ? "font-medium" : "text-muted"}`}
                        >
                          {status.replace(/_/g, " ")}
                        </span>
                      </div>
                    );
                  },
                )}
              </div>

              {/* Action Buttons */}
              {canAdvance && (
                <div
                  className="alert alert-info"
                  style={{ marginBottom: "16px" }}
                >
                  <span className="alert-icon">{statusInfo.icon}</span>
                  <div className="alert-content">
                    <strong>Next Step: {statusInfo.label}</strong>
                    <p className="text-sm">
                      Click the button below to update the job status.
                    </p>
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
                        Updating...
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
                    Cancel Job
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
                    <strong style={{ color: "var(--success)" }}>
                      Live Location Active
                    </strong>
                    <p
                      className="text-muted"
                      style={{ margin: 0, fontSize: "0.8rem" }}
                    >
                      Your location is being shared with the customer in
                      real-time
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Job Details */}
          <div className="card" style={{ marginTop: "24px" }}>
            <div className="card-header">
              <h3 className="card-title">Service Details</h3>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gap: "16px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px 0",
                    borderBottom: "1px solid var(--border-color)",
                  }}
                >
                  <span className="text-secondary">Category</span>
                  <strong style={{ textTransform: "capitalize" }}>
                    {job.category}
                  </strong>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px 0",
                    borderBottom: "1px solid var(--border-color)",
                  }}
                >
                  <span className="text-secondary">Urgency</span>
                  <span
                    className={`badge ${job.urgency === "high" ? "badge-danger" : job.urgency === "medium" ? "badge-warning" : "badge-secondary"}`}
                  >
                    {job.urgency}
                  </span>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px 0",
                    borderBottom: "1px solid var(--border-color)",
                  }}
                >
                  <span className="text-secondary">Created</span>
                  <strong>{new Date(job.created_at).toLocaleString()}</strong>
                </div>
                {job.assigned_at && (
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "12px 0",
                      borderBottom: "1px solid var(--border-color)",
                    }}
                  >
                    <span className="text-secondary">Assigned</span>
                    <strong>
                      {new Date(job.assigned_at).toLocaleString()}
                    </strong>
                  </div>
                )}
                {job.description && (
                  <div style={{ padding: "12px 0" }}>
                    <span className="text-secondary">Description</span>
                    <p style={{ marginTop: "8px" }}>{job.description}</p>
                  </div>
                )}
              </div>
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
              <div
                className="card-header"
                style={{
                  background:
                    job.status === "on_the_way"
                      ? "linear-gradient(135deg, #3B82F6, #1D4ED8)"
                      : "var(--card-header-bg)",
                }}
              >
                <h3
                  className="card-title"
                  style={{
                    color: job.status === "on_the_way" ? "white" : "inherit",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  {job.status === "on_the_way" && (
                    <span style={{ animation: "pulse 1s infinite" }}>📍</span>
                  )}
                  Navigation Map
                </h3>
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
              <h3 className="card-title">📍 Customer Location</h3>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gap: "12px" }}>
                <div>
                  <span className="text-secondary text-sm">Latitude</span>
                  <p className="font-semibold">
                    {job.location?.latitude || "N/A"}
                  </p>
                </div>
                <div>
                  <span className="text-secondary text-sm">Longitude</span>
                  <p className="font-semibold">
                    {job.location?.longitude || "N/A"}
                  </p>
                </div>
                {(job.live_eta_minutes || job.eta_minutes) && (
                  <div>
                    <span className="text-secondary text-sm">ETA</span>
                    <p className="font-semibold">
                      {job.live_eta_minutes || job.eta_minutes} minutes
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
                🗺️ Open in Maps
              </button>
            </div>
          </div>

          {/* Payment Info */}
          <div className="card" style={{ marginTop: "16px" }}>
            <div className="card-header">
              <h3 className="card-title">💰 Payment</h3>
            </div>
            <div className="card-body">
              <div style={{ textAlign: "center" }}>
                <div className="text-secondary text-sm">Estimated Price</div>
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
                    className={`badge ${job.payment_status === "paid" ? "badge-success" : "badge-warning"} mt-2`}
                  >
                    {job.payment_status}
                  </span>
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
              <h3 className="modal-title">Cancel Job</h3>
              <button
                className="modal-close"
                onClick={() => setShowCancelModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="alert alert-danger">
                <span className="alert-icon">⚠️</span>
                <div className="alert-content">
                  <strong>Warning</strong>
                  <p>
                    Cancelling jobs affects your reliability score and may
                    result in penalties.
                  </p>
                </div>
              </div>
              <p style={{ marginTop: "16px" }}>
                Are you sure you want to cancel this job?
              </p>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCancelModal(false)}
              >
                Keep Job
              </button>
              <button
                className="btn btn-danger"
                onClick={cancelJob}
                disabled={processing}
              >
                {processing ? "Cancelling..." : "Yes, Cancel Job"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
