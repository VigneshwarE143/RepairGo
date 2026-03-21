import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { serviceAPI } from "../../services/api";
import MapView from "../../components/MapView";

export default function RequestDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showPayModal, setShowPayModal] = useState(false);
  const [showRatingModal, setShowRatingModal] = useState(false);
  const [rating, setRating] = useState(5);
  const [processing, setProcessing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [suggestedTechnicians, setSuggestedTechnicians] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // Cancel booking state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancellationReasons, setCancellationReasons] = useState({});
  const [selectedCancelReason, setSelectedCancelReason] = useState("");
  const [cancelNotes, setCancelNotes] = useState("");

  // Live tracking state
  const [technicianLocation, setTechnicianLocation] = useState(null);
  const [trackingActive, setTrackingActive] = useState(false);

  useEffect(() => {
    loadRequest();
    loadCancellationReasons();
  }, [id]);

  // Poll service status every 10 seconds to catch technician status changes
  useEffect(() => {
    if (!request) return;
    const terminalStatuses = ["completed", "rated", "cancelled"];
    if (terminalStatuses.includes(request.status)) return;

    const interval = setInterval(async () => {
      try {
        const response = await serviceAPI.getMyRequests();
        const found = response.data?.find((r) => r._id === id);
        if (found) {
          setRequest(found);
        }
      } catch {
        // Silently handle polling errors
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [id, request?.status]);

  useEffect(() => {
    if (
      ["pending", "awaiting_technician_acceptance", "assigned"].includes(
        request?.status,
      )
    ) {
      loadSuggestedTechnicians();
    }
  }, [request]);

  // Live tracking - poll technician location when on_the_way, accepted, or in_progress
  useEffect(() => {
    if (["on_the_way", "accepted", "in_progress"].includes(request?.status)) {
      setTrackingActive(true);
      loadTechnicianLocation();
      const interval = setInterval(loadTechnicianLocation, 5000); // Update every 5 seconds
      return () => clearInterval(interval);
    } else {
      setTrackingActive(false);
      setTechnicianLocation(null);
    }
  }, [request?.status]);

  const loadTechnicianLocation = async () => {
    try {
      const response = await serviceAPI.getTechnicianLocation(id);
      setTechnicianLocation(response.data);
    } catch {
      // Location not available - technician might not be on the way yet
    }
  };

  const loadCancellationReasons = async () => {
    try {
      const response = await serviceAPI.getCancellationReasons();
      setCancellationReasons(response.data || {});
    } catch {
      // Use default reasons if endpoint unavailable
    }
  };

  const loadRequest = async () => {
    setLoading(true);
    try {
      const response = await serviceAPI.getMyRequests();
      const found = response.data?.find((r) => r._id === id);
      if (found) {
        setRequest(found);
      } else {
        toast.error("Request not found");
        navigate("/customer/my-requests");
      }
    } catch (error) {
      toast.error("Failed to load request");
    } finally {
      setLoading(false);
    }
  };

  const loadSuggestedTechnicians = async () => {
    setLoadingSuggestions(true);
    try {
      const response = await serviceAPI.getSuggestedTechnicians(id);
      setSuggestedTechnicians(response.data?.technicians || []);
    } catch {
      // Suggestions unavailable - may already be assigned
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handlePayment = async () => {
    setProcessing(true);
    try {
      await serviceAPI.pay(id, { payment_method: "card" });
      toast.success("Payment successful!");
      setShowPayModal(false);
      loadRequest();
    } catch (error) {
      toast.error(error.message || "Payment failed");
    } finally {
      setProcessing(false);
    }
  };

  const handleRating = async () => {
    setProcessing(true);
    try {
      await serviceAPI.rate(id, { rating });
      toast.success("Thanks for your rating!");
      setShowRatingModal(false);
      loadRequest();
    } catch (error) {
      toast.error(error.message || "Failed to submit rating");
    } finally {
      setProcessing(false);
    }
  };

  const chooseTechnician = async (technicianId) => {
    setConfirming(true);
    try {
      const response = await serviceAPI.chooseTechnician(id, {
        technician_id: technicianId,
      });
      toast.success(
        `Request sent to ${response.data?.technician_name || "technician"}! Waiting for acceptance. ETA: ~${response.data?.eta_minutes || "?"} min`,
      );
      loadRequest();
    } catch (error) {
      toast.error(
        error.response?.data?.detail ||
          error.message ||
          "Failed to send request",
      );
    } finally {
      setConfirming(false);
    }
  };

  const handleCancel = async () => {
    if (!selectedCancelReason) {
      toast.error("Please select a reason for cancellation");
      return;
    }
    setProcessing(true);
    try {
      await serviceAPI.cancel(id, {
        reason: selectedCancelReason,
        additional_notes: cancelNotes || null,
      });
      toast.success("Booking cancelled successfully");
      setShowCancelModal(false);
      loadRequest();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to cancel booking");
    } finally {
      setProcessing(false);
    }
  };

  const canCancel = () => {
    return [
      "pending",
      "awaiting_technician_acceptance",
      "assigned",
      "accepted",
    ].includes(request?.status);
  };

  const getStatusBadge = (status) => {
    const classes = {
      pending: "badge-pending",
      awaiting_technician_acceptance: "badge-warning",
      assigned: "badge-assigned",
      accepted: "badge-info",
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

  const getStatusTimeline = () => {
    const steps = [
      "pending",
      "awaiting_technician_acceptance",
      "assigned",
      "accepted",
      "on_the_way",
      "in_progress",
      "completed",
      "rated",
    ];
    const currentIndex = steps.indexOf(request?.status);

    return (
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: "24px",
        }}
      >
        {steps.map((step, index) => (
          <div key={step} style={{ textAlign: "center", flex: 1 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background:
                  index <= currentIndex ? "var(--success)" : "var(--gray-200)",
                color: index <= currentIndex ? "white" : "var(--gray-500)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 8px",
                fontSize: "0.875rem",
              }}
            >
              {index < currentIndex ? "✓" : index + 1}
            </div>
            <span
              className={`text-xs ${index <= currentIndex ? "" : "text-muted"}`}
            >
              {step.replace(/_/g, " ")}
            </span>
          </div>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="loading-page">
        <div className="loading-spinner lg"></div>
      </div>
    );
  }

  if (!request) {
    return null;
  }

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
        <h1>Request Details</h1>
        <p>Request ID: {request._id}</p>
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px" }}
      >
        {/* Main Details */}
        <div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Service Information</h3>
              {getStatusBadge(request.status)}
            </div>
            <div className="card-body">
              {getStatusTimeline()}

              <div style={{ marginTop: "32px", display: "grid", gap: "16px" }}>
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
                    {request.category}
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
                  <strong style={{ textTransform: "capitalize" }}>
                    {request.urgency}
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
                  <span className="text-secondary">Created</span>
                  <strong>
                    {new Date(request.created_at).toLocaleString()}
                  </strong>
                </div>
                {request.eta_minutes && (
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "12px 0",
                      borderBottom: "1px solid var(--border-color)",
                    }}
                  >
                    <span className="text-secondary">ETA</span>
                    <strong>{request.eta_minutes} minutes</strong>
                  </div>
                )}
                {request.description && (
                  <div style={{ padding: "12px 0" }}>
                    <span className="text-secondary">Description</span>
                    <p style={{ marginTop: "8px" }}>{request.description}</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Location */}
          <div className="card" style={{ marginTop: "24px" }}>
            <div className="card-header">
              <h3 className="card-title">Location</h3>
            </div>
            <div className="card-body">
              <div style={{ display: "flex", gap: "24px" }}>
                <div>
                  <span className="text-secondary">Latitude</span>
                  <p className="font-semibold">{request.location?.latitude}</p>
                </div>
                <div>
                  <span className="text-secondary">Longitude</span>
                  <p className="font-semibold">{request.location?.longitude}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Live Tracking - Ola/Rapido Style */}
          {trackingActive && technicianLocation && (
            <div className="card" style={{ marginTop: "24px" }}>
              <div
                className="card-header"
                style={{
                  background: "linear-gradient(135deg, #4CAF50, #2196F3)",
                }}
              >
                <h3
                  className="card-title"
                  style={{
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <span style={{ animation: "pulse 1s infinite" }}>📍</span>
                  Live Tracking
                </h3>
                <span
                  className="badge badge-success"
                  style={{ background: "white", color: "#4CAF50" }}
                >
                  {request.status === "on_the_way" ? "On The Way" : "Accepted"}
                </span>
              </div>
              <div className="card-body" style={{ padding: "24px" }}>
                {/* Technician Info */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "16px",
                    marginBottom: "20px",
                  }}
                >
                  <div
                    style={{
                      width: "60px",
                      height: "60px",
                      borderRadius: "50%",
                      background: "var(--primary-bg)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "1.5rem",
                    }}
                  >
                    👨‍🔧
                  </div>
                  <div>
                    <h4 style={{ margin: 0 }}>
                      {technicianLocation.technician_name || "Technician"}
                    </h4>
                    <p className="text-muted" style={{ margin: "4px 0 0" }}>
                      {request.category} Specialist
                    </p>
                  </div>
                </div>

                {/* ETA Display - Big and prominent */}
                <div
                  style={{
                    textAlign: "center",
                    padding: "24px",
                    background:
                      "linear-gradient(135deg, var(--primary-bg), var(--success-bg))",
                    borderRadius: "12px",
                    marginBottom: "20px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "3rem",
                      fontWeight: "bold",
                      color: "var(--primary)",
                    }}
                  >
                    {technicianLocation.eta_minutes || "?"} min
                  </div>
                  <div className="text-muted">Estimated Time of Arrival</div>
                  {technicianLocation.distance_km && (
                    <div style={{ marginTop: "8px", fontSize: "0.9rem" }}>
                      📍 {technicianLocation.distance_km.toFixed(1)} km away
                    </div>
                  )}
                </div>

                {/* Live Stats */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: "16px",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      padding: "12px",
                      background: "var(--background)",
                      borderRadius: "8px",
                    }}
                  >
                    <div style={{ fontSize: "1.2rem", fontWeight: "bold" }}>
                      {technicianLocation.speed_kmh?.toFixed(0) || 0} km/h
                    </div>
                    <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                      Speed
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "12px",
                      background: "var(--background)",
                      borderRadius: "8px",
                    }}
                  >
                    <div style={{ fontSize: "1.2rem", fontWeight: "bold" }}>
                      {technicianLocation.heading
                        ? `${technicianLocation.heading}°`
                        : "N/A"}
                    </div>
                    <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                      Direction
                    </div>
                  </div>
                  <div
                    style={{
                      padding: "12px",
                      background: "var(--background)",
                      borderRadius: "8px",
                    }}
                  >
                    <div style={{ fontSize: "1.2rem", fontWeight: "bold" }}>
                      {technicianLocation.accuracy_meters?.toFixed(0) || "?"} m
                    </div>
                    <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                      GPS Accuracy
                    </div>
                  </div>
                </div>

                {/* Live Map View - Ola/Rapido Style */}
                <div style={{ marginTop: "20px" }}>
                  <MapView
                    technicianPosition={
                      technicianLocation.latitude &&
                      technicianLocation.longitude
                        ? [
                            technicianLocation.latitude,
                            technicianLocation.longitude,
                          ]
                        : null
                    }
                    customerPosition={
                      request.location?.latitude && request.location?.longitude
                        ? [
                            request.location.latitude,
                            request.location.longitude,
                          ]
                        : null
                    }
                    technicianName={
                      technicianLocation.technician_name || "Technician"
                    }
                    customerAddress={request.address || "Your Location"}
                    eta={technicianLocation.eta_minutes}
                    distance={technicianLocation.distance_km}
                    speed={technicianLocation.speed_kmh}
                    heading={technicianLocation.heading}
                    status={request.status}
                    mode="customer"
                    height="350px"
                  />
                </div>

                {/* Last updated */}
                <p
                  style={{
                    textAlign: "center",
                    marginTop: "16px",
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                  }}
                >
                  Last updated: {new Date().toLocaleTimeString()} •
                  Auto-refreshing every 5 seconds
                </p>
              </div>
            </div>
          )}

          {/* Assigned Technician Info (when not tracking) */}
          {request.technician &&
            !trackingActive &&
            request.status !== "pending" && (
              <div className="card" style={{ marginTop: "24px" }}>
                <div className="card-header">
                  <h3 className="card-title">Assigned Technician</h3>
                </div>
                <div className="card-body">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "16px",
                    }}
                  >
                    <div
                      style={{
                        width: "50px",
                        height: "50px",
                        borderRadius: "50%",
                        background: "var(--primary-bg)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "1.25rem",
                      }}
                    >
                      👨‍🔧
                    </div>
                    <div>
                      <h4 style={{ margin: 0 }}>
                        {request.technician.name || "Technician"}
                      </h4>
                      <div
                        style={{
                          display: "flex",
                          gap: "12px",
                          marginTop: "4px",
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        {request.technician.rating && (
                          <span>⭐ {request.technician.rating.toFixed(1)}</span>
                        )}
                        {request.technician.completed_jobs !== undefined && (
                          <span>
                            ✅ {request.technician.completed_jobs} jobs
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

          {/* Suggested Technicians (ML-powered) */}
          {["pending", "awaiting_technician_acceptance", "assigned"].includes(
            request.status,
          ) && (
            <div className="card" style={{ marginTop: "24px" }}>
              <div className="card-header">
                <h3 className="card-title">🤖 ML-Recommended Technician</h3>
              </div>
              <div className="card-body">
                {loadingSuggestions ? (
                  <div style={{ textAlign: "center", padding: "24px" }}>
                    <div className="loading-spinner"></div>
                    <p className="text-muted" style={{ marginTop: "8px" }}>
                      Analyzing available technicians with ML model...
                    </p>
                  </div>
                ) : suggestedTechnicians.length > 0 ? (
                  <div style={{ display: "grid", gap: "16px" }}>
                    {/* Best ML Recommendation */}
                    <div
                      style={{
                        padding: "20px",
                        borderRadius: "12px",
                        background:
                          "linear-gradient(135deg, var(--success-bg), var(--primary-bg))",
                        border: "2px solid var(--success)",
                        position: "relative",
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          top: "-10px",
                          left: "16px",
                          background: "var(--success)",
                          color: "white",
                          padding: "4px 12px",
                          borderRadius: "20px",
                          fontSize: "0.75rem",
                          fontWeight: "bold",
                        }}
                      >
                        🏆 ML Best Match
                      </div>
                      <div
                        style={{
                          marginTop: "8px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                        }}
                      >
                        <div>
                          <h4
                            style={{ fontSize: "1.25rem", marginBottom: "8px" }}
                          >
                            {suggestedTechnicians[0].name}
                          </h4>
                          <div
                            style={{
                              display: "flex",
                              gap: "16px",
                              fontSize: "0.875rem",
                              flexWrap: "wrap",
                            }}
                          >
                            <span>
                              ⭐{" "}
                              {suggestedTechnicians[0].rating?.toFixed(1) ||
                                "N/A"}{" "}
                              rating
                            </span>
                            <span>
                              ✅ {suggestedTechnicians[0].completed_jobs} jobs
                              completed
                            </span>
                            <span>
                              📍{" "}
                              {suggestedTechnicians[0].distance_km?.toFixed(
                                1,
                              ) || "?"}{" "}
                              km away
                            </span>
                            <span>
                              ⏱️ ETA: ~{suggestedTechnicians[0].eta_minutes} min
                            </span>
                          </div>
                          <div
                            style={{ marginTop: "8px", fontSize: "0.875rem" }}
                          >
                            <strong>Skills:</strong>{" "}
                            {suggestedTechnicians[0].skills?.join(", ")}
                          </div>
                        </div>
                        <div style={{ textAlign: "center", minWidth: "80px" }}>
                          <div
                            style={{
                              fontSize: "2rem",
                              fontWeight: "bold",
                              color: "var(--success)",
                              lineHeight: "1",
                            }}
                          >
                            {Math.round(
                              suggestedTechnicians[0].predicted_success * 100,
                            )}
                            %
                          </div>
                          <div
                            style={{
                              fontSize: "0.7rem",
                              color: "var(--text-muted)",
                            }}
                          >
                            ML Confidence
                          </div>
                          <div
                            style={{
                              marginTop: "4px",
                              fontSize: "0.65rem",
                              padding: "2px 6px",
                              background: "var(--primary-bg)",
                              borderRadius: "4px",
                              color: "var(--primary)",
                            }}
                          >
                            {suggestedTechnicians[0].prediction_source ===
                            "model"
                              ? "Neural Network"
                              : "Heuristic"}
                          </div>
                        </div>
                      </div>
                      <p
                        style={{
                          marginTop: "12px",
                          fontSize: "0.8rem",
                          color: "var(--success)",
                          fontWeight: "500",
                        }}
                      >
                        ✨ Best match identified. Confirm to assign and notify
                        the technician.
                      </p>
                      {request.status === "pending" && (
                        <button
                          className="btn btn-primary"
                          style={{ marginTop: "8px" }}
                          onClick={() =>
                            chooseTechnician(suggestedTechnicians[0].id)
                          }
                          disabled={confirming}
                        >
                          {confirming
                            ? "Sending Request..."
                            : "Choose & Send Request"}
                        </button>
                      )}
                      {request.status === "awaiting_technician_acceptance" && (
                        <div
                          style={{
                            marginTop: "12px",
                            padding: "8px 16px",
                            background: "var(--warning-bg)",
                            borderRadius: "8px",
                            fontSize: "0.85rem",
                            color: "var(--warning)",
                            fontWeight: 500,
                          }}
                        >
                          ⏳ Waiting for technician to accept...
                        </div>
                      )}
                    </div>

                    {/* Other Available Technicians */}
                    {suggestedTechnicians.length > 1 && (
                      <div style={{ marginTop: "8px" }}>
                        <h4
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--text-secondary)",
                            marginBottom: "12px",
                          }}
                        >
                          📋 Other Available Technicians (
                          {suggestedTechnicians.length - 1})
                        </h4>
                        <div style={{ display: "grid", gap: "8px" }}>
                          {suggestedTechnicians.slice(1).map((tech) => (
                            <div
                              key={tech.id}
                              style={{
                                padding: "12px 16px",
                                borderRadius: "8px",
                                background: "var(--background)",
                                border: "1px solid var(--border-color)",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                              }}
                            >
                              <div>
                                <strong style={{ fontSize: "0.95rem" }}>
                                  {tech.name}
                                </strong>
                                <div
                                  style={{
                                    display: "flex",
                                    gap: "12px",
                                    marginTop: "4px",
                                    fontSize: "0.8rem",
                                    color: "var(--text-muted)",
                                  }}
                                >
                                  <span>⭐ {tech.rating?.toFixed(1)}</span>
                                  <span>✅ {tech.completed_jobs} jobs</span>
                                  <span>
                                    📍 {tech.distance_km?.toFixed(1)} km
                                  </span>
                                  <span>⏱️ ~{tech.eta_minutes} min</span>
                                </div>
                              </div>
                              <div style={{ textAlign: "right" }}>
                                <div
                                  style={{
                                    fontSize: "1rem",
                                    fontWeight: "bold",
                                    color: "var(--primary)",
                                  }}
                                >
                                  {Math.round(tech.predicted_success * 100)}%
                                </div>
                                <div
                                  style={{
                                    fontSize: "0.65rem",
                                    color: "var(--text-muted)",
                                  }}
                                >
                                  confidence
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: "24px" }}>
                    <p className="text-muted">
                      No technicians available for this category right now.
                    </p>
                    <p
                      className="text-muted"
                      style={{ fontSize: "0.875rem", marginTop: "8px" }}
                    >
                      We'll notify you once one becomes available.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div>
          {/* Pricing */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Pricing</h3>
            </div>
            <div className="card-body">
              {request.estimated_price && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "12px",
                  }}
                >
                  <span className="text-secondary">Estimated</span>
                  <span>₹{request.estimated_price.toFixed(2)}</span>
                </div>
              )}
              {request.final_price && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "1.25rem",
                  }}
                >
                  <strong>Final Price</strong>
                  <strong className="text-primary">
                    ₹{request.final_price.toFixed(2)}
                  </strong>
                </div>
              )}
              {request.payment_status && (
                <div style={{ marginTop: "16px" }}>
                  <span
                    className={`badge ${request.payment_status === "paid" ? "badge-success" : "badge-warning"}`}
                  >
                    Payment: {request.payment_status}
                  </span>
                </div>
              )}
            </div>
            {request.status === "completed" &&
              request.payment_status !== "paid" && (
                <div className="card-footer">
                  <button
                    className="btn btn-primary btn-block"
                    onClick={() => setShowPayModal(true)}
                  >
                    💳 Pay Now
                  </button>
                </div>
              )}
          </div>

          {/* Cancel Booking Button */}
          {canCancel() && (
            <div className="card" style={{ marginTop: "16px" }}>
              <div className="card-body" style={{ textAlign: "center" }}>
                <p
                  className="text-muted"
                  style={{ marginBottom: "12px", fontSize: "0.875rem" }}
                >
                  Need to cancel this booking?
                </p>
                <button
                  className="btn btn-block"
                  style={{
                    background: "var(--danger-bg)",
                    color: "var(--danger)",
                    border: "1px solid var(--danger)",
                  }}
                  onClick={() => setShowCancelModal(true)}
                >
                  ❌ Cancel Booking
                </button>
              </div>
            </div>
          )}

          {/* Cancelled Status Info */}
          {request.status === "cancelled" && (
            <div
              className="card"
              style={{ marginTop: "16px", borderColor: "var(--danger)" }}
            >
              <div
                className="card-header"
                style={{ background: "var(--danger-bg)" }}
              >
                <h3 className="card-title" style={{ color: "var(--danger)" }}>
                  Booking Cancelled
                </h3>
              </div>
              <div className="card-body">
                {request.cancellation_reason && (
                  <div style={{ marginBottom: "12px" }}>
                    <span className="text-secondary">Reason:</span>
                    <p style={{ marginTop: "4px", fontWeight: 500 }}>
                      {cancellationReasons[request.cancellation_reason] ||
                        request.cancellation_reason}
                    </p>
                  </div>
                )}
                {request.cancellation_notes && (
                  <div>
                    <span className="text-secondary">Additional Notes:</span>
                    <p style={{ marginTop: "4px" }}>
                      {request.cancellation_notes}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Rating */}
          {request.status === "completed" &&
            request.payment_status === "paid" &&
            !request.rating && (
              <div className="card" style={{ marginTop: "16px" }}>
                <div className="card-header">
                  <h3 className="card-title">Rate Service</h3>
                </div>
                <div className="card-body" style={{ textAlign: "center" }}>
                  <p className="text-secondary mb-4">
                    How was your experience?
                  </p>
                  <button
                    className="btn btn-primary"
                    onClick={() => setShowRatingModal(true)}
                  >
                    ⭐ Leave a Rating
                  </button>
                </div>
              </div>
            )}

          {request.rating && (
            <div className="card" style={{ marginTop: "16px" }}>
              <div className="card-header">
                <h3 className="card-title">Your Rating</h3>
              </div>
              <div className="card-body" style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2rem" }}>
                  {"⭐".repeat(request.rating)}
                </div>
                <p className="text-secondary">{request.rating}/5 stars</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Payment Modal */}
      {showPayModal && (
        <div className="modal-overlay" onClick={() => setShowPayModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Complete Payment</h3>
              <button
                className="modal-close"
                onClick={() => setShowPayModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <div style={{ fontSize: "3rem", marginBottom: "16px" }}>💳</div>
                <h3 style={{ marginBottom: "8px" }}>
                  Total: $
                  {request.final_price?.toFixed(2) ||
                    request.estimated_price?.toFixed(2)}
                </h3>
                <p className="text-secondary">
                  Click confirm to process payment
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowPayModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handlePayment}
                disabled={processing}
              >
                {processing ? "Processing..." : "Confirm Payment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rating Modal */}
      {showRatingModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowRatingModal(false)}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Rate Your Experience</h3>
              <button
                className="modal-close"
                onClick={() => setShowRatingModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <div
                  className="rating"
                  style={{ justifyContent: "center", gap: "8px" }}
                >
                  {[1, 2, 3, 4, 5].map((star) => (
                    <span
                      key={star}
                      className={`rating-star ${star <= rating ? "filled" : ""}`}
                      onClick={() => setRating(star)}
                      style={{ fontSize: "2.5rem", cursor: "pointer" }}
                    >
                      ⭐
                    </span>
                  ))}
                </div>
                <p className="text-secondary" style={{ marginTop: "16px" }}>
                  {rating === 5
                    ? "Excellent!"
                    : rating === 4
                      ? "Great!"
                      : rating === 3
                        ? "Good"
                        : rating === 2
                          ? "Fair"
                          : "Poor"}
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowRatingModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleRating}
                disabled={processing}
              >
                {processing ? "Submitting..." : "Submit Rating"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel Modal */}
      {showCancelModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowCancelModal(false)}
        >
          <div
            className="modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "500px" }}
          >
            <div
              className="modal-header"
              style={{ background: "var(--danger-bg)" }}
            >
              <h3 className="modal-title" style={{ color: "var(--danger)" }}>
                Cancel Booking
              </h3>
              <button
                className="modal-close"
                onClick={() => setShowCancelModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: "16px" }}>
                Please select a reason for cancellation:
              </p>

              <div style={{ display: "grid", gap: "8px" }}>
                {Object.entries(cancellationReasons).map(([key, label]) => (
                  <label
                    key={key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      padding: "12px 16px",
                      border:
                        selectedCancelReason === key
                          ? "2px solid var(--danger)"
                          : "1px solid var(--border-color)",
                      borderRadius: "8px",
                      cursor: "pointer",
                      background:
                        selectedCancelReason === key
                          ? "var(--danger-bg)"
                          : "white",
                    }}
                  >
                    <input
                      type="radio"
                      name="cancelReason"
                      value={key}
                      checked={selectedCancelReason === key}
                      onChange={(e) => setSelectedCancelReason(e.target.value)}
                      style={{ marginRight: "12px" }}
                    />
                    {label}
                  </label>
                ))}
              </div>

              <div style={{ marginTop: "16px" }}>
                <label className="form-label">
                  Additional Notes (optional)
                </label>
                <textarea
                  className="input"
                  rows={3}
                  placeholder="Any additional details..."
                  value={cancelNotes}
                  onChange={(e) => setCancelNotes(e.target.value)}
                  style={{ resize: "vertical" }}
                ></textarea>
              </div>

              <div
                style={{
                  marginTop: "16px",
                  padding: "12px",
                  background: "var(--warning-bg)",
                  borderRadius: "8px",
                  fontSize: "0.875rem",
                }}
              >
                ⚠️ <strong>Note:</strong> Cancellation may affect future service
                availability. Please only cancel if absolutely necessary.
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowCancelModal(false);
                  setSelectedCancelReason("");
                  setCancelNotes("");
                }}
              >
                Keep Booking
              </button>
              <button
                className="btn"
                style={{ background: "var(--danger)", color: "white" }}
                onClick={handleCancel}
                disabled={processing || !selectedCancelReason}
              >
                {processing ? "Cancelling..." : "Confirm Cancellation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
