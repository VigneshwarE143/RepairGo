import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { serviceAPI } from "../../services/api";

export default function MyRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    loadRequests();
  }, []);

  const loadRequests = async () => {
    setLoading(true);
    try {
      const response = await serviceAPI.getMyRequests();
      setRequests(response.data || []);
    } catch (error) {
      toast.error("Failed to load requests");
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const classes = {
      pending: "badge-pending",
      assigned: "badge-assigned",
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

  const filteredRequests =
    filter === "all" ? requests : requests.filter((r) => r.status === filter);

  return (
    <div>
      <div className="page-header">
        <h1>Requests</h1>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: "24px" }}>
        <div className="card-body" style={{ padding: "16px 24px" }}>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {[
              "all",
              "pending",
              "assigned",
              "in_progress",
              "completed",
              "rated",
            ].map((status) => (
              <button
                key={status}
                className={`btn ${filter === status ? "btn-primary" : "btn-secondary"} btn-sm`}
                onClick={() => setFilter(status)}
              >
                {status === "all" ? "All" : status.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Requests List */}
      {loading ? (
        <div className="loading-page">
          <div className="loading-spinner lg"></div>
        </div>
      ) : filteredRequests.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <h3>No requests</h3>
            <Link to="/customer/new-request" className="btn btn-primary">
              New Request
            </Link>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: "16px" }}>
          {filteredRequests.map((request) => (
            <div key={request._id} className="request-card">
              <div className="request-header">
                <div
                  style={{ display: "flex", alignItems: "center", gap: "8px" }}
                >
                  <span className="request-category">{request.category}</span>
                  <span
                    className="badge badge-secondary"
                    style={{ textTransform: "capitalize" }}
                  >
                    {request.urgency}
                  </span>
                </div>
                {getStatusBadge(request.status)}
              </div>

              <div className="request-meta">
                <span className="request-meta-item">
                  {new Date(request.created_at).toLocaleDateString()}
                </span>
                {request.eta_minutes && (
                  <span className="request-meta-item">
                    ETA {request.eta_minutes}m
                  </span>
                )}
                {request.technician_id && (
                  <span className="request-meta-item">Tech assigned</span>
                )}
              </div>

              {request.description && (
                <details style={{ marginTop: "8px" }}>
                  <summary className="text-secondary text-sm">Details</summary>
                  <p
                    className="request-description"
                    style={{ marginTop: "8px" }}
                  >
                    {request.description}
                  </p>
                </details>
              )}

              <div className="request-footer">
                <div>
                  {request.final_price ? (
                    <span className="request-price">
                      ₹{request.final_price.toFixed(2)}
                    </span>
                  ) : request.estimated_price ? (
                    <span className="text-secondary">
                      ₹{request.estimated_price.toFixed(2)}
                    </span>
                  ) : null}
                </div>
                <Link
                  to={`/customer/request/${request._id}`}
                  className="btn btn-primary btn-sm"
                >
                  View
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
