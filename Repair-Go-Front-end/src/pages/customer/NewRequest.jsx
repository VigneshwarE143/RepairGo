import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { serviceAPI } from "../../services/api";

const CATEGORIES = [
  {
    value: "Plumbing",
    label: "Plumbing",
    icon: "🔧",
    description: "Pipes, leaks, fixtures, drains",
  },
  {
    value: "Electrical",
    label: "Electrical",
    icon: "⚡",
    description: "Wiring, outlets, switches, lights",
  },
  {
    value: "HVAC",
    label: "HVAC",
    icon: "❄️",
    description: "Heating, cooling, ventilation",
  },
  {
    value: "Appliance Repair",
    label: "Appliance Repair",
    icon: "🔌",
    description: "Washer, dryer, refrigerator",
  },
  {
    value: "Roofing",
    label: "Roofing",
    icon: "🏠",
    description: "Roof repair, gutters, shingles",
  },
  {
    value: "Painting",
    label: "Painting",
    icon: "🎨",
    description: "Interior, exterior painting",
  },
  {
    value: "Carpentry",
    label: "Carpentry",
    icon: "🪚",
    description: "Wood work, furniture, doors",
  },
  {
    value: "Locksmith",
    label: "Locksmith",
    icon: "🔐",
    description: "Locks, keys, security",
  },
];

const URGENCY_LEVELS = [
  {
    value: "low",
    label: "Low",
    description: "Can wait a few days",
    addon: "+₹0",
  },
  {
    value: "medium",
    label: "Medium",
    description: "Within 24 hours",
    addon: "+₹10",
  },
  {
    value: "high",
    label: "High",
    description: "ASAP - Emergency",
    addon: "+₹25",
  },
];

export default function NewRequest() {
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [estimating, setEstimating] = useState(false);
  const [estimate, setEstimate] = useState(null);
  const [step, setStep] = useState(1);
  const [serviceId, setServiceId] = useState(null);
  const [suggestedTechnicians, setSuggestedTechnicians] = useState([]);
  const [selectedTechnicianId, setSelectedTechnicianId] = useState(null);
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
    setValue,
  } = useForm({
    defaultValues: {
      category: "",
      urgency: "medium",
      description: "",
      latitude: "",
      longitude: "",
    },
  });

  const selectedCategory = watch("category");
  const selectedUrgency = watch("urgency");

  const getLocationFromBrowser = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setValue("latitude", position.coords.latitude.toString());
          setValue("longitude", position.coords.longitude.toString());
          toast.success("Location detected!");
        },
        (error) => {
          toast.error("Could not get location. Please enter manually.");
        },
      );
    } else {
      toast.error("Geolocation not supported by your browser");
    }
  };

  const getEstimate = async (data) => {
    setEstimating(true);
    try {
      const response = await serviceAPI.estimate({
        category: data.category,
        urgency: data.urgency,
        location: {
          latitude: parseFloat(data.latitude) || 0,
          longitude: parseFloat(data.longitude) || 0,
        },
      });
      setEstimate(response.data.estimate);
      setStep(3);
    } catch (error) {
      toast.error(error.message || "Failed to get estimate");
    } finally {
      setEstimating(false);
    }
  };

  const onSubmit = async (data) => {
    if (step === 2) {
      await getEstimate(data);
      return;
    }

    setLoading(true);
    try {
      const response = await serviceAPI.create({
        category: data.category,
        urgency: data.urgency,
        description: data.description,
        location: {
          latitude: parseFloat(data.latitude) || 0,
          longitude: parseFloat(data.longitude) || 0,
        },
      });

      // Store service ID and suggested technicians
      setServiceId(response.data?.id);

      if (
        response.data?.has_recommendation &&
        response.data?.suggested_technicians?.length > 0
      ) {
        setSuggestedTechnicians(response.data.suggested_technicians);
        setSelectedTechnicianId(
          response.data.suggested_technicians[0].technician_id,
        );
        setStep(4); // Go to technician selection step
        toast.success("Top technicians found! Please choose one.");
      } else {
        // No recommendation available, navigate to requests
        toast.info("Service request created. We're finding a technician...");
        navigate("/customer/my-requests");
      }
    } catch (error) {
      toast.error(error.message || "Failed to create request");
    } finally {
      setLoading(false);
    }
  };

  const confirmBooking = async () => {
    if (!serviceId) {
      toast.error("Service ID not found");
      return;
    }
    if (!selectedTechnicianId) {
      toast.error("Please select a technician");
      return;
    }

    setConfirming(true);
    try {
      const response = await serviceAPI.chooseTechnician(serviceId, {
        technician_id: selectedTechnicianId,
      });
      toast.success(
        `Request sent to ${response.data?.technician_name || "technician"}! Waiting for acceptance. ETA: ~${response.data?.eta_minutes || "?"} min`,
      );
      navigate("/customer/my-requests");
    } catch (error) {
      toast.error(error.message || "Failed to send request to technician");
    } finally {
      setConfirming(false);
    }
  };

  const cancelBooking = async () => {
    if (serviceId) {
      try {
        await serviceAPI.cancel(serviceId, { reason: "changed_mind" });
        toast.info("Request cancelled");
      } catch {
        // Silently continue - service might already be cancelled or modified
      }
    }
    navigate("/customer/my-requests");
  };

  return (
    <div>
      <div className="page-header">
        <h1>Create Service Request</h1>
        <p>Tell us what you need help with</p>
      </div>

      {/* Progress Steps */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          marginBottom: "32px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: step >= s ? "var(--primary)" : "var(--gray-200)",
                  color: step >= s ? "white" : "var(--text-muted)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 600,
                }}
              >
                {s}
              </div>
              <span className={step >= s ? "font-medium" : "text-muted"}>
                {s === 1
                  ? "Service"
                  : s === 2
                    ? "Location"
                    : s === 3
                      ? "Estimate"
                      : "Confirm"}
              </span>
              {s < 4 && (
                <div
                  style={{
                    width: 40,
                    height: 2,
                    background: step > s ? "var(--primary)" : "var(--gray-200)",
                  }}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ maxWidth: 700, margin: "0 auto" }}>
        <div className="card-body">
          <form onSubmit={handleSubmit(onSubmit)}>
            {/* Step 1: Select Category & Urgency */}
            {step === 1 && (
              <>
                <div className="form-group">
                  <label className="form-label required">
                    Service Category
                  </label>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(180px, 1fr))",
                      gap: "12px",
                    }}
                  >
                    {CATEGORIES.map((cat) => (
                      <label
                        key={cat.value}
                        className={`request-card ${selectedCategory === cat.value ? "active" : ""}`}
                        style={{
                          cursor: "pointer",
                          border:
                            selectedCategory === cat.value
                              ? "2px solid var(--primary)"
                              : undefined,
                          background:
                            selectedCategory === cat.value
                              ? "var(--primary-bg)"
                              : undefined,
                        }}
                      >
                        <input
                          type="radio"
                          value={cat.value}
                          {...register("category", {
                            required: "Please select a category",
                          })}
                          style={{ display: "none" }}
                        />
                        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>
                          {cat.icon}
                        </div>
                        <h4>{cat.label}</h4>
                        <p className="text-secondary text-sm">
                          {cat.description}
                        </p>
                      </label>
                    ))}
                  </div>
                  {errors.category && (
                    <span className="form-error">
                      {errors.category.message}
                    </span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label required">Urgency Level</label>
                  <div
                    style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}
                  >
                    {URGENCY_LEVELS.map((level) => (
                      <label
                        key={level.value}
                        className="request-card"
                        style={{
                          flex: 1,
                          minWidth: 140,
                          cursor: "pointer",
                          textAlign: "center",
                          border:
                            selectedUrgency === level.value
                              ? "2px solid var(--primary)"
                              : undefined,
                          background:
                            selectedUrgency === level.value
                              ? "var(--primary-bg)"
                              : undefined,
                        }}
                      >
                        <input
                          type="radio"
                          value={level.value}
                          {...register("urgency")}
                          style={{ display: "none" }}
                        />
                        <h4>{level.label}</h4>
                        <p className="text-secondary text-sm">
                          {level.description}
                        </p>
                        <span
                          className="badge badge-primary"
                          style={{ marginTop: "8px" }}
                        >
                          {level.addon}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-textarea"
                    rows={4}
                    placeholder="Describe your issue in detail..."
                    {...register("description")}
                  />
                </div>

                <button
                  type="button"
                  className="btn btn-primary btn-block btn-lg"
                  onClick={() => selectedCategory && setStep(2)}
                  disabled={!selectedCategory}
                >
                  Continue →
                </button>
              </>
            )}

            {/* Step 2: Location */}
            {step === 2 && (
              <>
                <div style={{ textAlign: "center", marginBottom: "24px" }}>
                  <div style={{ fontSize: "3rem", marginBottom: "16px" }}>
                    📍
                  </div>
                  <h3>Where do you need service?</h3>
                  <p className="text-secondary">
                    We'll find technicians near your location
                  </p>
                </div>

                <button
                  type="button"
                  className="btn btn-outline btn-block btn-lg"
                  onClick={getLocationFromBrowser}
                  style={{ marginBottom: "24px" }}
                >
                  📍 Use My Current Location
                </button>

                <div
                  className="text-center text-muted"
                  style={{ marginBottom: "24px" }}
                >
                  — or enter manually —
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "16px",
                  }}
                >
                  <div className="form-group">
                    <label className="form-label required">Latitude</label>
                    <input
                      type="number"
                      step="any"
                      className={`form-input ${errors.latitude ? "error" : ""}`}
                      placeholder="e.g., 40.7128"
                      {...register("latitude", {
                        required: "Latitude is required",
                      })}
                    />
                    {errors.latitude && (
                      <span className="form-error">
                        {errors.latitude.message}
                      </span>
                    )}
                  </div>
                  <div className="form-group">
                    <label className="form-label required">Longitude</label>
                    <input
                      type="number"
                      step="any"
                      className={`form-input ${errors.longitude ? "error" : ""}`}
                      placeholder="e.g., -74.0060"
                      {...register("longitude", {
                        required: "Longitude is required",
                      })}
                    />
                    {errors.longitude && (
                      <span className="form-error">
                        {errors.longitude.message}
                      </span>
                    )}
                  </div>
                </div>

                <div
                  style={{ display: "flex", gap: "12px", marginTop: "24px" }}
                >
                  <button
                    type="button"
                    className="btn btn-secondary btn-lg"
                    onClick={() => setStep(1)}
                  >
                    ← Back
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary btn-lg"
                    style={{ flex: 1 }}
                    disabled={estimating}
                  >
                    {estimating ? (
                      <>
                        <span className="loading-spinner sm"></span>
                        Getting Estimate...
                      </>
                    ) : (
                      "Get Price Estimate →"
                    )}
                  </button>
                </div>
              </>
            )}

            {/* Step 3: Confirm & Submit */}
            {step === 3 && estimate && (
              <>
                <div style={{ textAlign: "center", marginBottom: "24px" }}>
                  <div style={{ fontSize: "3rem", marginBottom: "16px" }}>
                    ✅
                  </div>
                  <h3>Your Estimate</h3>
                </div>

                <div
                  className="card"
                  style={{ background: "var(--gray-50)", marginBottom: "24px" }}
                >
                  <div className="card-body">
                    <div style={{ display: "grid", gap: "16px" }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>Base Price:</span>
                        <strong>₹{estimate.base_price?.toFixed(2)}</strong>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>Travel Cost:</span>
                        <strong>₹{estimate.travel_cost?.toFixed(2)}</strong>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>Urgency Addon:</span>
                        <strong>₹{estimate.urgency_addon?.toFixed(2)}</strong>
                      </div>
                      {estimate.surge_multiplier > 1 && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            color: "var(--warning)",
                          }}
                        >
                          <span>Surge ({estimate.surge_multiplier}x):</span>
                          <strong>Applied</strong>
                        </div>
                      )}
                      <hr
                        style={{
                          border: "none",
                          borderTop: "1px solid var(--border-color)",
                        }}
                      />
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "1.5rem",
                        }}
                      >
                        <span>Total Estimate:</span>
                        <strong className="text-primary">
                          ₹{estimate.final_price?.toFixed(2)}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="alert alert-info">
                  <span className="alert-icon">ℹ️</span>
                  <div className="alert-content">
                    This is an estimate. Final price may vary based on actual
                    work required.
                  </div>
                </div>

                <div
                  style={{ display: "flex", gap: "12px", marginTop: "24px" }}
                >
                  <button
                    type="button"
                    className="btn btn-secondary btn-lg"
                    onClick={() => setStep(2)}
                  >
                    ← Back
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary btn-lg"
                    style={{ flex: 1 }}
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <span className="loading-spinner sm"></span>
                        Finding Best Technician...
                      </>
                    ) : (
                      "Find Best Technician →"
                    )}
                  </button>
                </div>
              </>
            )}

            {/* Step 4: Choose Technician from Top 3 */}
            {step === 4 && suggestedTechnicians.length > 0 && (
              <>
                <div style={{ textAlign: "center", marginBottom: "24px" }}>
                  <div style={{ fontSize: "3rem", marginBottom: "16px" }}>
                    🎯
                  </div>
                  <h3>Choose Your Technician</h3>
                  <p className="text-secondary">
                    Our ML system ranked the best technicians for you. Select
                    one to send a request.
                  </p>
                </div>

                <div
                  style={{ display: "grid", gap: "16px", marginBottom: "24px" }}
                >
                  {suggestedTechnicians.map((tech, index) => (
                    <div
                      key={tech.technician_id}
                      onClick={() =>
                        setSelectedTechnicianId(tech.technician_id)
                      }
                      style={{
                        padding: "20px",
                        borderRadius: "12px",
                        cursor: "pointer",
                        border:
                          selectedTechnicianId === tech.technician_id
                            ? "2px solid var(--primary)"
                            : "1px solid var(--border-color)",
                        background:
                          selectedTechnicianId === tech.technician_id
                            ? "linear-gradient(135deg, var(--primary-bg) 0%, #f0f9ff 100%)"
                            : "var(--background)",
                        position: "relative",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {index === 0 && (
                        <div
                          style={{
                            position: "absolute",
                            top: "-10px",
                            left: "16px",
                            background: "var(--success)",
                            color: "white",
                            padding: "3px 10px",
                            borderRadius: "20px",
                            fontSize: "0.7rem",
                            fontWeight: "bold",
                          }}
                        >
                          ML Best Match
                        </div>
                      )}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "16px",
                        }}
                      >
                        {/* Avatar */}
                        <div
                          style={{
                            width: 52,
                            height: 52,
                            borderRadius: "50%",
                            background:
                              index === 0
                                ? "var(--primary)"
                                : index === 1
                                  ? "var(--info)"
                                  : "var(--gray-400)",
                            color: "white",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "1.25rem",
                            fontWeight: 700,
                            flexShrink: 0,
                          }}
                        >
                          {tech.name?.charAt(0) || "#"}
                        </div>

                        {/* Info */}
                        <div style={{ flex: 1 }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "4px",
                            }}
                          >
                            <h4 style={{ margin: 0 }}>{tech.name}</h4>
                            <span
                              style={{
                                color: "var(--warning)",
                                fontSize: "0.85rem",
                              }}
                            >
                              ⭐ {tech.rating?.toFixed(1) || "New"}
                            </span>
                            <span
                              className="text-secondary"
                              style={{ fontSize: "0.8rem" }}
                            >
                              • {tech.completed_jobs || 0} jobs
                            </span>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              gap: "16px",
                              fontSize: "0.8rem",
                              color: "var(--text-muted)",
                              flexWrap: "wrap",
                            }}
                          >
                            <span>🚗 ~{Math.round(tech.eta_minutes)} min</span>
                            <span>📍 {tech.distance_km?.toFixed(1)} km</span>
                            <span>🤖 {tech.ml_score}% match</span>
                          </div>
                          {tech.skills?.length > 0 && (
                            <div style={{ marginTop: "6px" }}>
                              {tech.skills.map((skill, i) => (
                                <span
                                  key={i}
                                  className="badge badge-secondary"
                                  style={{
                                    marginRight: "6px",
                                    fontSize: "0.7rem",
                                  }}
                                >
                                  {skill}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Selection indicator */}
                        <div
                          style={{
                            width: 24,
                            height: 24,
                            borderRadius: "50%",
                            border:
                              selectedTechnicianId === tech.technician_id
                                ? "2px solid var(--primary)"
                                : "2px solid var(--gray-300)",
                            background:
                              selectedTechnicianId === tech.technician_id
                                ? "var(--primary)"
                                : "transparent",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "white",
                            fontSize: "0.75rem",
                            flexShrink: 0,
                          }}
                        >
                          {selectedTechnicianId === tech.technician_id && "✓"}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Price Summary */}
                {estimate && (
                  <div
                    style={{
                      padding: "16px",
                      background: "var(--gray-50)",
                      borderRadius: "12px",
                      border: "1px solid var(--border-color)",
                      marginBottom: "24px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span>Estimated Price:</span>
                      <strong
                        style={{
                          fontSize: "1.5rem",
                          color: "var(--primary)",
                        }}
                      >
                        ₹{estimate.final_price?.toFixed(2)}
                      </strong>
                    </div>
                  </div>
                )}

                <div
                  className="alert alert-info"
                  style={{ marginBottom: "24px" }}
                >
                  <span className="alert-icon">ℹ️</span>
                  <div className="alert-content">
                    After you select a technician, they will need to accept the
                    job before the booking is confirmed.
                  </div>
                </div>

                <div
                  style={{ display: "flex", gap: "12px", marginTop: "24px" }}
                >
                  <button
                    type="button"
                    className="btn btn-secondary btn-lg"
                    onClick={cancelBooking}
                    disabled={confirming}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-lg"
                    style={{ flex: 1 }}
                    onClick={confirmBooking}
                    disabled={confirming || !selectedTechnicianId}
                  >
                    {confirming ? (
                      <>
                        <span className="loading-spinner sm"></span>
                        Sending Request...
                      </>
                    ) : (
                      "✓ Send Request to Technician"
                    )}
                  </button>
                </div>
              </>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
