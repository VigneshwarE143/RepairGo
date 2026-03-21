import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { adminAPI, mlAPI } from "../../services/api";

export default function FraudManagement() {
  const [fraudFlags, setFraudFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [selectedFlag, setSelectedFlag] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    loadFraudFlags();
  }, []);

  const loadFraudFlags = async () => {
    setLoading(true);
    try {
      const response = await mlAPI.getFraudFlags();
      setFraudFlags(response.data || []);
    } catch (error) {
      // Demo data if API unavailable
      setFraudFlags([
        {
          _id: "1",
          type: "price_anomaly",
          severity: "high",
          description: "Unusually high price for service category",
          job_id: "job123",
          detected_at: new Date().toISOString(),
          status: "pending",
          risk_score: 0.85,
        },
        {
          _id: "2",
          type: "location_mismatch",
          severity: "medium",
          description: "Technician location does not match job area",
          job_id: "job456",
          detected_at: new Date(Date.now() - 86400000).toISOString(),
          status: "reviewed",
          risk_score: 0.65,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const runFraudScan = async () => {
    setScanning(true);
    try {
      // Call ML fraud scan endpoint
      const response = await mlAPI.fraudScan();

      toast.success(
        `Fraud scan complete. ${response.data?.flagged_count || 0} suspicious items flagged.`,
      );
      loadFraudFlags();
    } catch (error) {
      toast.error("Fraud scan failed");
    } finally {
      setScanning(false);
    }
  };

  const resolveFraudFlag = async (flagId, action) => {
    try {
      await mlAPI.updateFraudFlagStatus(flagId, action);
      toast.success(`Flag marked as ${action}`);
      loadFraudFlags();
    } catch (error) {
      toast.error("Failed to resolve flag");
    }
  };

  const getSeverityBadge = (severity) => {
    const classes = {
      low: "badge-success",
      medium: "badge-warning",
      high: "badge-danger",
    };
    return (
      <span className={`badge ${classes[severity] || "badge-secondary"}`}>
        {severity}
      </span>
    );
  };

  const getStatusBadge = (status) => {
    const classes = {
      pending: "badge-warning",
      reviewed: "badge-info",
      resolved: "badge-success",
      dismissed: "badge-secondary",
    };
    return (
      <span className={`badge ${classes[status] || "badge-secondary"}`}>
        {status}
      </span>
    );
  };

  const pendingCount = fraudFlags.filter((f) => f.status === "pending").length;
  const highSeverityCount = fraudFlags.filter(
    (f) => f.severity === "high",
  ).length;

  if (loading) {
    return (
      <div className="loading-page">
        <div className="loading-spinner lg"></div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Fraud Detection</h1>
        <p>Monitor and manage fraud alerts powered by ML</p>
        <div className="page-header-actions">
          <button
            className="btn btn-primary"
            onClick={runFraudScan}
            disabled={scanning}
          >
            {scanning ? (
              <>
                <span className="loading-spinner sm"></span>
                Scanning...
              </>
            ) : (
              "🔍 Run Fraud Scan"
            )}
          </button>
        </div>
      </div>

      {/* Alert Stats */}
      <div className="stats-grid" style={{ marginBottom: "24px" }}>
        <div className="stat-card">
          <div className="stat-icon warning">⚠️</div>
          <div className="stat-content">
            <div className="stat-value">{pendingCount}</div>
            <div className="stat-label">Pending Review</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon danger">🚨</div>
          <div className="stat-content">
            <div className="stat-value">{highSeverityCount}</div>
            <div className="stat-label">High Severity</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon info">📊</div>
          <div className="stat-content">
            <div className="stat-value">{fraudFlags.length}</div>
            <div className="stat-label">Total Flags</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon success">✅</div>
          <div className="stat-content">
            <div className="stat-value">
              {fraudFlags.filter((f) => f.status === "resolved").length}
            </div>
            <div className="stat-label">Resolved</div>
          </div>
        </div>
      </div>

      {/* Fraud Flags Table */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">🚩 Fraud Alerts</h3>
          <button className="btn btn-ghost btn-sm" onClick={loadFraudFlags}>
            🔄 Refresh
          </button>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Severity</th>
                <th>Risk Score</th>
                <th>Status</th>
                <th>Detected</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {fraudFlags.length === 0 ? (
                <tr>
                  <td
                    colSpan="6"
                    style={{ textAlign: "center", padding: "48px" }}
                  >
                    <div className="empty-state" style={{ padding: 0 }}>
                      <div className="empty-state-icon">✅</div>
                      <h3>No Fraud Alerts</h3>
                      <p className="text-muted">
                        No suspicious activity detected
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                fraudFlags.map((flag) => (
                  <tr key={flag._id}>
                    <td>
                      <div>
                        <div
                          className="font-medium"
                          style={{ textTransform: "capitalize" }}
                        >
                          {flag.type?.replace(/_/g, " ")}
                        </div>
                        <div className="text-sm text-muted">
                          {flag.description}
                        </div>
                      </div>
                    </td>
                    <td>{getSeverityBadge(flag.severity)}</td>
                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <div className="progress" style={{ width: "60px" }}>
                          <div
                            className={`progress-bar ${flag.risk_score > 0.7 ? "danger" : flag.risk_score > 0.4 ? "warning" : "success"}`}
                            style={{ width: `${flag.risk_score * 100}%` }}
                          ></div>
                        </div>
                        <span>{(flag.risk_score * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td>{getStatusBadge(flag.status)}</td>
                    <td>{new Date(flag.detected_at).toLocaleDateString()}</td>
                    <td>
                      {flag.status === "pending" ? (
                        <div className="dropdown">
                          <button className="btn btn-ghost btn-sm dropdown-toggle">
                            Actions ▾
                          </button>
                          <div className="dropdown-content">
                            <button
                              className="dropdown-item"
                              onClick={() => {
                                setSelectedFlag(flag);
                                setShowDetailModal(true);
                              }}
                            >
                              🔍 View Details
                            </button>
                            <button
                              className="dropdown-item"
                              onClick={() =>
                                resolveFraudFlag(flag._id, "resolved")
                              }
                            >
                              ✅ Mark Resolved
                            </button>
                            <button
                              className="dropdown-item"
                              onClick={() =>
                                resolveFraudFlag(flag._id, "dismissed")
                              }
                            >
                              ❌ Dismiss
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            setSelectedFlag(flag);
                            setShowDetailModal(true);
                          }}
                        >
                          View
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal */}
      {showDetailModal && selectedFlag && (
        <div
          className="modal-overlay"
          onClick={() => setShowDetailModal(false)}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">🚩 Fraud Alert Details</h3>
              <button
                className="modal-close"
                onClick={() => setShowDetailModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div
                className={`alert alert-${selectedFlag.severity === "high" ? "danger" : selectedFlag.severity === "medium" ? "warning" : "info"}`}
              >
                <span className="alert-icon">
                  {selectedFlag.severity === "high" ? "🚨" : "⚠️"}
                </span>
                <div className="alert-content">
                  <strong style={{ textTransform: "capitalize" }}>
                    {selectedFlag.type?.replace(/_/g, " ")}
                  </strong>
                  <p>{selectedFlag.description}</p>
                </div>
              </div>

              <div style={{ display: "grid", gap: "16px", marginTop: "24px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px",
                    background: "var(--gray-50)",
                    borderRadius: "8px",
                  }}
                >
                  <span>Risk Score</span>
                  <strong
                    style={{
                      color:
                        selectedFlag.risk_score > 0.7
                          ? "var(--danger)"
                          : "var(--warning)",
                    }}
                  >
                    {(selectedFlag.risk_score * 100).toFixed(0)}%
                  </strong>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px",
                    background: "var(--gray-50)",
                    borderRadius: "8px",
                  }}
                >
                  <span>Severity</span>
                  {getSeverityBadge(selectedFlag.severity)}
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px",
                    background: "var(--gray-50)",
                    borderRadius: "8px",
                  }}
                >
                  <span>Status</span>
                  {getStatusBadge(selectedFlag.status)}
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "12px",
                    background: "var(--gray-50)",
                    borderRadius: "8px",
                  }}
                >
                  <span>Detected At</span>
                  <strong>
                    {new Date(selectedFlag.detected_at).toLocaleString()}
                  </strong>
                </div>
                {selectedFlag.job_id && (
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "12px",
                      background: "var(--gray-50)",
                      borderRadius: "8px",
                    }}
                  >
                    <span>Related Job</span>
                    <code>{selectedFlag.job_id}</code>
                  </div>
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowDetailModal(false)}
              >
                Close
              </button>
              {selectedFlag.status === "pending" && (
                <>
                  <button
                    className="btn btn-outline"
                    onClick={() => {
                      resolveFraudFlag(selectedFlag._id, "dismissed");
                      setShowDetailModal(false);
                    }}
                  >
                    Dismiss
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      resolveFraudFlag(selectedFlag._id, "resolved");
                      setShowDetailModal(false);
                    }}
                  >
                    Mark Resolved
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
