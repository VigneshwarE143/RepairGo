import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { serviceAPI, mlAPI } from "../../services/api";
import toast from "react-hot-toast";

export default function CustomerDashboard() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [demandInfo, setDemandInfo] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Get demand prediction for pricing info
      const demandRes = await mlAPI.predictDemand({});
      setDemandInfo(demandRes.data);
    } catch {
      // Demand info unavailable - not critical
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

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <div className="page-header-actions">
          <Link to="/customer/new-request" className="btn btn-primary btn-lg">
            New Request
          </Link>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon primary">📍</div>
          <div className="stat-content">
            <div className="stat-value">Live</div>
            <div className="stat-label">Tracking ready</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon success">✓</div>
          <div className="stat-content">
            <div className="stat-value">Verified</div>
            <div className="stat-label">Technicians</div>
          </div>
        </div>
        {demandInfo && (
          <div className="stat-card">
            <div
              className={`stat-icon ${demandInfo.demand_level === "high" ? "danger" : demandInfo.demand_level === "low" ? "success" : "info"}`}
            >
              📊
            </div>
            <div className="stat-content">
              <div
                className="stat-value"
                style={{ textTransform: "capitalize" }}
              >
                {demandInfo.demand_level}
              </div>
              <div className="stat-label">x{demandInfo.multiplier}</div>
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: "24px" }}>
        <div className="card-header">
          <h3 className="card-title">Quick Book</h3>
        </div>
        <div className="card-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "12px",
            }}
          >
            {[
              { label: "Plumbing", icon: "🔧" },
              { label: "Electrical", icon: "⚡" },
              { label: "HVAC", icon: "❄️" },
              { label: "General", icon: "🏠" },
            ].map((item) => (
              <Link
                key={item.label}
                to="/customer/new-request"
                className="request-card"
                style={{ textDecoration: "none", textAlign: "center" }}
              >
                <div style={{ fontSize: "1.75rem", marginBottom: "8px" }}>
                  {item.icon}
                </div>
                <h4 style={{ fontSize: "0.95rem" }}>{item.label}</h4>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
