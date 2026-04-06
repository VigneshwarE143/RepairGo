import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { serviceAPI, technicianAPI } from "../../services/api";

export default function TechnicianJobs() {
  const [jobs, setJobs] = useState([]);
  const [pendingJobs, setPendingJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingPending, setLoadingPending] = useState(true);
  const [filter, setFilter] = useState("active");
  const [respondingTo, setRespondingTo] = useState(null);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [selectedJobForReject, setSelectedJobForReject] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const REJECT_REASONS = [
    { value: "too_far", label: "Too far from location" },
    { value: "busy_with_other_job", label: "Busy with another job" },
    { value: "out_of_service_area", label: "Out of service area" },
    { value: "equipment_unavailable", label: "Equipment unavailable" },
    { value: "personal_emergency", label: "Personal emergency" },
    { value: "other", label: "Other reason" },
  ];
  const [estimatedArrival, setEstimatedArrival] = useState(30);

  useEffect(() => {
    loadJobs();
    loadPendingJobs();
  }, []);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const response = await technicianAPI.getMyJobs();
      setJobs(response.data || []);
    } catch (error) {
      toast.error("Failed to load jobs");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  const loadPendingJobs = async () => {
    setLoadingPending(true);
    try {
      const response = await technicianAPI.getPendingJobs();
      setPendingJobs(response.data || []);
    } catch {
      setPendingJobs([]);
    } finally {
      setLoadingPending(false);
    }
  };

  const handleAcceptJob = async (jobId, isNewFlow = false) => {
    setRespondingTo(jobId);
    try {
      if (isNewFlow) {
        // New flow: awaiting_technician_acceptance → use technician-response endpoint
        await technicianAPI.respondToRequest(jobId, {
          action: "accept",
          estimated_arrival_minutes: estimatedArrival,
        });
      } else {
        // Legacy flow: assigned → use respond endpoint
        await technicianAPI.respondToJob(jobId, {
          action: "accept",
          estimated_arrival_minutes: estimatedArrival,
        });
      }
      toast.success("Job accepted! Customer has been notified.");
      loadPendingJobs();
      loadJobs();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to accept job");
    } finally {
      setRespondingTo(null);
    }
  };

  const handleRejectJob = async () => {
    if (!rejectReason) {
      toast.error("Please select a reason for rejection");
      return;
    }
    const jobId = selectedJobForReject;
    setRespondingTo(jobId);
    try {
      // Determine if job is new flow (awaiting_technician_acceptance) or legacy (assigned)
      const job = pendingJobs.find((j) => j._id === jobId);
      const isNewFlow = job?.status === "awaiting_technician_acceptance";

      if (isNewFlow) {
        await technicianAPI.respondToRequest(jobId, {
          action: "reject",
          reject_reason: rejectReason,
        });
      } else {
        await technicianAPI.respondToJob(jobId, {
          action: "reject",
          reject_reason: rejectReason,
        });
      }
      toast.success(
        "Job rejected. Customer will be reassigned a new technician.",
      );
      setShowRejectModal(false);
      setSelectedJobForReject(null);
      setRejectReason("");
      loadPendingJobs();
      loadJobs();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to reject job");
    } finally {
      setRespondingTo(null);
    }
  };

  const openRejectModal = (jobId) => {
    setSelectedJobForReject(jobId);
    setShowRejectModal(true);
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
      <span className={`badge ${classes[status] || "badge-secondary"}`}>
        {status?.replace(/_/g, " ")}
      </span>
    );
  };

  const filteredJobs = jobs.filter((job) => {
    if (filter === "active") {
      return [
        "awaiting_technician_acceptance",
        "assigned",
        "accepted",
        "on_the_way",
        "in_progress",
      ].includes(job.status);
    } else if (filter === "completed") {
      return ["completed", "rated"].includes(job.status);
    }
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <h1>Jobs</h1>
      </div>

      {/* Pending Jobs - Need Accept/Reject */}
      {!loadingPending && pendingJobs.length > 0 && (
        <div
          className="card"
          style={{
            marginBottom: "24px",
            borderColor: "var(--warning)",
            borderWidth: "2px",
          }}
        >
          <div
            className="card-header"
            style={{ background: "var(--warning-bg)" }}
          >
            <h3
              className="card-title"
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              <span style={{ animation: "pulse 1s infinite" }}>🔔</span>
              Requests ({pendingJobs.length})
            </h3>
          </div>
          <div className="card-body">
            <div style={{ display: "grid", gap: "16px" }}>
              {pendingJobs.map((job) => (
                <div
                  key={job._id}
                  style={{
                    padding: "20px",
                    border: "1px solid var(--border-color)",
                    borderRadius: "12px",
                    background: "var(--background)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "12px",
                          marginBottom: "8px",
                        }}
                      >
                        <h4 style={{ margin: 0, textTransform: "capitalize" }}>
                          {job.category}
                        </h4>
                        <span
                          className={`badge ${
                            job.urgency === "high"
                              ? "badge-danger"
                              : job.urgency === "medium"
                                ? "badge-warning"
                                : "badge-secondary"
                          }`}
                        >
                          {job.urgency} priority
                        </span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          gap: "16px",
                          fontSize: "0.875rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        <span>₹{job.estimated_price?.toFixed(2) || "TBD"}</span>
                        <span>
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                        {job.eta_minutes && <span>ETA {job.eta_minutes}m</span>}
                      </div>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        marginLeft: "16px",
                      }}
                    >
                      <button
                        className="btn btn-success"
                        onClick={() =>
                          handleAcceptJob(
                            job._id,
                            job.status === "awaiting_technician_acceptance",
                          )
                        }
                        disabled={respondingTo === job._id}
                      >
                        {respondingTo === job._id ? "..." : "✓ Accept"}
                      </button>
                      <button
                        className="btn btn-ghost"
                        style={{ color: "var(--danger)" }}
                        onClick={() => openRejectModal(job._id)}
                        disabled={respondingTo === job._id}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: "24px" }}>
        <div className="card-body" style={{ padding: "16px 24px" }}>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className={`btn ${filter === "active" ? "btn-primary" : "btn-secondary"} btn-sm`}
              onClick={() => setFilter("active")}
            >
              Active Jobs
            </button>
            <button
              className={`btn ${filter === "completed" ? "btn-primary" : "btn-secondary"} btn-sm`}
              onClick={() => setFilter("completed")}
            >
              Completed
            </button>
            <button
              className={`btn ${filter === "all" ? "btn-primary" : "btn-secondary"} btn-sm`}
              onClick={() => setFilter("all")}
            >
              All Jobs
            </button>
          </div>
        </div>
      </div>

      {/* Jobs List */}
      {loading ? (
        <div className="loading-page">
          <div className="loading-spinner lg"></div>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <h3>No jobs</h3>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Price</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => (
                  <tr key={job._id}>
                    <td style={{ textTransform: "capitalize" }}>
                      <span style={{ marginRight: "8px", fontWeight: 600 }}>
                        {job.category}
                      </span>
                      <span
                        className={`badge ${job.urgency === "high" ? "badge-danger" : job.urgency === "medium" ? "badge-warning" : "badge-secondary"}`}
                      >
                        {job.urgency}
                      </span>
                    </td>
                    <td>{getStatusBadge(job.status)}</td>
                    <td>₹{job.estimated_price?.toFixed(2) || "0.00"}</td>
                    <td>
                      <Link
                        to={`/technician/job/${job._id}`}
                        className="btn btn-primary btn-sm"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Reject Job Modal */}
      {showRejectModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowRejectModal(false)}
        >
          <div
            className="modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "450px" }}
          >
            <div
              className="modal-header"
              style={{ background: "var(--danger-bg)" }}
            >
              <h3 className="modal-title" style={{ color: "var(--danger)" }}>
                Reject Job
              </h3>
              <button
                className="modal-close"
                onClick={() => setShowRejectModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Reason for Rejection *</label>
                <select
                  className="input"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  required
                  style={{ padding: "10px 12px" }}
                >
                  <option value="">-- Select a reason --</option>
                  {REJECT_REASONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowRejectModal(false);
                  setSelectedJobForReject(null);
                  setRejectReason("");
                }}
              >
                Cancel
              </button>
              <button
                className="btn"
                style={{ background: "var(--danger)", color: "white" }}
                onClick={handleRejectJob}
                disabled={
                  respondingTo === selectedJobForReject || !rejectReason
                }
              >
                {respondingTo === selectedJobForReject ? "..." : "Reject"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
