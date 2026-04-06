import { useState, useEffect } from "react";
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
  const [paymentMethod, setPaymentMethod] = useState("upi");
  const [upiPaymentData, setUpiPaymentData] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [suggestedTechnicians, setSuggestedTechnicians] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancellationReasons, setCancellationReasons] = useState({});
  const [selectedCancelReason, setSelectedCancelReason] = useState("");
  const [cancelNotes, setCancelNotes] = useState("");

  const [technicianLocation, setTechnicianLocation] = useState(null);
  const [trackingActive, setTrackingActive] = useState(false);

  useEffect(() => {
    loadRequest();
    loadCancellationReasons();
  }, [id]);

  useEffect(() => {
    if (!request) return;
    const isTerminal =
      request.status === "cancelled" ||
      request.status === "rated" ||
      (request.status === "completed" && request.payment_status === "paid");
    if (isTerminal) return;

    const interval = setInterval(async () => {
      try {
        const response = await serviceAPI.getById(id);
        const found = response.data;
        if (found) {
          setRequest((prev) => ({ ...prev, ...found }));
          if (
            ["accepted", "on_the_way", "in_progress"].includes(found.status)
          ) {
            loadTechnicianLocation();
          }
        }
      } catch {
        // Silently handle polling errors
      }
    }, 4000);

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

  useEffect(() => {
    if (["on_the_way", "accepted", "in_progress"].includes(request?.status)) {
      setTrackingActive(true);
      loadTechnicianLocation();
      const interval = setInterval(loadTechnicianLocation, 5000);
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
      // Location not available
    }
  };

  const loadCancellationReasons = async () => {
    try {
      const response = await serviceAPI.getCancellationReasons();
      setCancellationReasons(response.data || {});
    } catch {
      // Use defaults if endpoint unavailable
    }
  };

  const loadRequest = async () => {
    setLoading(true);
    try {
      const response = await serviceAPI.getById(id);
      const found = response.data;
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
      // Suggestions unavailable
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handlePayment = async () => {
    setProcessing(true);
    try {
      if (paymentMethod === "cash") {
        await serviceAPI.pay(id, { payment_method: "cash" });
        toast.success("Payment marked as Cash");
        setShowPayModal(false);
        setUpiPaymentData(null);
        loadRequest();
        return;
      }

      const response = await serviceAPI.pay(id, { payment_method: "upi" });
      setUpiPaymentData(response.data || null);
      toast.success("Scan QR and pay using any UPI app");
    } catch (error) {
      toast.error(error.message || "Payment failed");
    } finally {
      setProcessing(false);
    }
  };

  const markUpiPaid = async () => {
    setProcessing(true);
    try {
      await serviceAPI.pay(id, {
        payment_method: "upi",
        customer_paid: true,
      });
      toast.success("Marked as paid. Waiting for technician confirmation.");
      setShowPayModal(false);
      setUpiPaymentData(null);
      loadRequest();
    } catch (error) {
      toast.error(error.message || "Failed to mark payment");
    } finally {
      setProcessing(false);
    }
  };

  const getPaymentStatusLabel = (status) => {
    if (status === "paid") return "Paid";
    if (status === "pending_confirmation") return "Waiting for Confirmation";
    return "Pending";
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

  const displayAmount = (() => {
    const fromUpiResponse = Number(upiPaymentData?.amount);
    if (Number.isFinite(fromUpiResponse) && fromUpiResponse > 0) {
      return fromUpiResponse;
    }
    const fromFinal = Number(request?.final_price);
    if (Number.isFinite(fromFinal) && fromFinal > 0) {
      return fromFinal;
    }
    const fromEstimated = Number(request?.estimated_price);
    if (Number.isFinite(fromEstimated) && fromEstimated > 0) {
      return fromEstimated;
    }
    return null;
  })();

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
        <h1>Request</h1>
        <p className="text-muted text-sm">#{request._id}</p>
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px" }}
      >
        <div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Overview</h3>
              {getStatusBadge(request.status)}
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
                    {request.category}
                  </div>
                </div>
                <div>
                  <div className="text-secondary text-xs">Urgency</div>
                  <div
                    className="font-semibold"
                    style={{ textTransform: "capitalize" }}
                  >
                    {request.urgency}
                  </div>
                </div>
                <div>
                  <div className="text-secondary text-xs">Created</div>
                  <div className="font-semibold">
                    {new Date(request.created_at).toLocaleDateString()}
                  </div>
                </div>
                {request.eta_minutes && (
                  <div>
                    <div className="text-secondary text-xs">ETA</div>
                    <div className="font-semibold">{request.eta_minutes}m</div>
                  </div>
                )}
              </div>
              {request.description && (
                <details style={{ marginTop: "16px" }}>
                  <summary className="text-secondary text-sm">Details</summary>
                  <p style={{ marginTop: "8px" }}>{request.description}</p>
                </details>
              )}
            </div>
          </div>

          {trackingActive && technicianLocation && (
            <div className="card" style={{ marginTop: "24px" }}>
              <div className="card-header">
                <h3 className="card-title">Tracking</h3>
                <span className="badge badge-success">
                  {request.status === "on_the_way" ? "On the way" : "Accepted"}
                </span>
              </div>
              <div
                className="card-body"
                style={{ display: "grid", gap: "12px" }}
              >
                <div
                  style={{ display: "flex", alignItems: "center", gap: "12px" }}
                >
                  <div
                    style={{
                      width: "44px",
                      height: "44px",
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
                    <div className="font-semibold">
                      {technicianLocation.technician_name || "Technician"}
                    </div>
                    <div className="text-muted text-sm">{request.category}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                  <span className="badge badge-info">
                    ETA {technicianLocation.eta_minutes || "?"}m
                  </span>
                  {technicianLocation.distance_km && (
                    <span className="badge badge-secondary">
                      {technicianLocation.distance_km.toFixed(1)} km
                    </span>
                  )}
                </div>
                <MapView
                  technicianPosition={
                    technicianLocation.latitude && technicianLocation.longitude
                      ? [
                          technicianLocation.latitude,
                          technicianLocation.longitude,
                        ]
                      : null
                  }
                  customerPosition={
                    request.location?.latitude && request.location?.longitude
                      ? [request.location.latitude, request.location.longitude]
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
                  height="340px"
                />
              </div>
            </div>
          )}

          {request.technician &&
            !trackingActive &&
            request.status !== "pending" && (
              <div className="card" style={{ marginTop: "24px" }}>
                <div className="card-header">
                  <h3 className="card-title">Technician</h3>
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
                          <span>{request.technician.completed_jobs} jobs</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

          {["pending", "awaiting_technician_acceptance", "assigned"].includes(
            request.status,
          ) && (
            <div className="card" style={{ marginTop: "24px" }}>
              <div className="card-header">
                <h3 className="card-title">Suggested Technicians</h3>
              </div>
              <div className="card-body">
                {loadingSuggestions ? (
                  <div style={{ textAlign: "center", padding: "24px" }}>
                    <div className="loading-spinner"></div>
                  </div>
                ) : suggestedTechnicians.length > 0 ? (
                  <div style={{ display: "grid", gap: "12px" }}>
                    {suggestedTechnicians.map((tech, index) => (
                      <div
                        key={tech.technician_id || tech.id || index}
                        style={{
                          padding: "12px 16px",
                          borderRadius: "12px",
                          border: "1px solid var(--border-color)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          background:
                            index === 0
                              ? "linear-gradient(135deg, var(--success-bg), var(--primary-bg))"
                              : "var(--white)",
                        }}
                      >
                        <div>
                          <div className="font-semibold">{tech.name}</div>
                          <div
                            className="text-muted text-xs"
                            style={{ marginTop: "4px" }}
                          >
                            ⭐ {tech.rating?.toFixed(1) || "N/A"} •{" "}
                            {tech.eta_minutes}m • {tech.distance_km?.toFixed(1)}{" "}
                            km
                          </div>
                        </div>
                        <div
                          style={{
                            display: "flex",
                            gap: "8px",
                            alignItems: "center",
                          }}
                        >
                          <span className="badge badge-secondary">
                            {Math.round(tech.predicted_success * 100)}%
                          </span>
                          {request.status === "pending" && index === 0 && (
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() =>
                                chooseTechnician(tech.technician_id || tech.id)
                              }
                              disabled={confirming}
                            >
                              {confirming ? "..." : "Choose"}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                    {request.status === "awaiting_technician_acceptance" && (
                      <div
                        className="alert alert-warning"
                        style={{ marginBottom: 0 }}
                      >
                        <span className="alert-icon">⏳</span>
                        <div className="alert-content">
                          <strong>Waiting for acceptance</strong>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: "24px" }}>
                    <p className="text-muted">No technicians available</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Payment</h3>
            </div>
            <div className="card-body">
              <div
                style={{ display: "flex", alignItems: "baseline", gap: "8px" }}
              >
                <div className="text-secondary text-xs">Amount</div>
                <div className="request-price">
                  ₹{displayAmount?.toFixed(2) || "0.00"}
                </div>
              </div>
              {request.payment_status && (
                <div style={{ marginTop: "12px" }}>
                  <span
                    className={`badge ${
                      request.payment_status === "paid"
                        ? "badge-success"
                        : request.payment_status === "pending_confirmation"
                          ? "badge-info"
                          : "badge-warning"
                    }`}
                  >
                    {getPaymentStatusLabel(request.payment_status)}
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
                    Pay
                  </button>
                </div>
              )}
          </div>

          {canCancel() && (
            <div className="card" style={{ marginTop: "16px" }}>
              <div className="card-body" style={{ textAlign: "center" }}>
                <button
                  className="btn btn-block"
                  style={{
                    background: "var(--danger-bg)",
                    color: "var(--danger)",
                    border: "1px solid var(--danger)",
                  }}
                  onClick={() => setShowCancelModal(true)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

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
                  Cancelled
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

          {request.status === "completed" &&
            request.payment_status === "paid" &&
            !request.rating && (
              <div className="card" style={{ marginTop: "16px" }}>
                <div className="card-header">
                  <h3 className="card-title">Rate</h3>
                </div>
                <div className="card-body" style={{ textAlign: "center" }}>
                  <button
                    className="btn btn-primary"
                    onClick={() => setShowRatingModal(true)}
                  >
                    Rate
                  </button>
                </div>
              </div>
            )}

          {request.rating && (
            <div className="card" style={{ marginTop: "16px" }}>
              <div className="card-header">
                <h3 className="card-title">Rating</h3>
              </div>
              <div className="card-body" style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2rem" }}>
                  {"⭐".repeat(request.rating)}
                </div>
                <p className="text-secondary">{request.rating}/5</p>
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
              <h3 className="modal-title">Payment</h3>
              <button
                className="modal-close"
                onClick={() => setShowPayModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>
                  💳
                </div>
                <h3 style={{ marginBottom: "8px" }}>
                  ₹{displayAmount?.toFixed(2) || "0.00"}
                </h3>
                {!upiPaymentData && (
                  <>
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        justifyContent: "center",
                      }}
                    >
                      <button
                        className={`btn ${paymentMethod === "cash" ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => setPaymentMethod("cash")}
                        type="button"
                      >
                        Cash
                      </button>
                      <button
                        className={`btn ${paymentMethod === "upi" ? "btn-primary" : "btn-secondary"}`}
                        onClick={() => setPaymentMethod("upi")}
                        type="button"
                      >
                        UPI
                      </button>
                    </div>
                  </>
                )}

                {upiPaymentData && (
                  <div style={{ marginTop: "16px" }}>
                    <p className="text-secondary">Scan & pay</p>
                    <img
                      src={`data:image/png;base64,${upiPaymentData.qr_code}`}
                      alt="UPI QR"
                      style={{
                        width: 220,
                        height: 220,
                        borderRadius: 8,
                        border: "1px solid var(--border-color)",
                      }}
                    />
                    <p style={{ marginTop: "8px" }}>
                      UPI ID: <strong>{upiPaymentData.upi_id}</strong>
                    </p>
                  </div>
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowPayModal(false);
                  setUpiPaymentData(null);
                }}
              >
                Cancel
              </button>
              {!upiPaymentData ? (
                <button
                  className="btn btn-primary"
                  onClick={handlePayment}
                  disabled={processing}
                >
                  {processing ? "..." : "Continue"}
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  onClick={markUpiPaid}
                  disabled={processing}
                >
                  {processing ? "..." : "I Have Paid"}
                </button>
              )}
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
              <h3 className="modal-title">Rate</h3>
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
                {processing ? "..." : "Submit"}
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
                Cancel
              </h3>
              <button
                className="modal-close"
                onClick={() => setShowCancelModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: "16px" }}>Reason</p>

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
                <label className="form-label">Notes (optional)</label>
                <textarea
                  className="input"
                  rows={3}
                  placeholder="Any additional details..."
                  value={cancelNotes}
                  onChange={(e) => setCancelNotes(e.target.value)}
                  style={{ resize: "vertical" }}
                ></textarea>
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
                Keep
              </button>
              <button
                className="btn"
                style={{ background: "var(--danger)", color: "white" }}
                onClick={handleCancel}
                disabled={processing || !selectedCancelReason}
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
