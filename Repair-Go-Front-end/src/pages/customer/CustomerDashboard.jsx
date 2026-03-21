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
        <h1>Welcome to RepairGo</h1>
        <p>Get your repairs done quickly and efficiently</p>
        <div className="page-header-actions">
          <Link to="/customer/new-request" className="btn btn-primary btn-lg">
            ➕ Create New Request
          </Link>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon primary">📋</div>
          <div className="stat-content">
            <div className="stat-value">Quick Service</div>
            <div className="stat-label">Get help in minutes</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon success">✓</div>
          <div className="stat-content">
            <div className="stat-value">Verified Techs</div>
            <div className="stat-label">Professional technicians</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon warning">💰</div>
          <div className="stat-content">
            <div className="stat-value">Fair Pricing</div>
            <div className="stat-label">Transparent estimates</div>
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
                {demandInfo.demand_level} Demand
              </div>
              <div className="stat-label">
                Price multiplier: {demandInfo.multiplier}x
              </div>
            </div>
          </div>
        )}
      </div>

      {/* How It Works */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">How It Works</h3>
        </div>
        <div className="card-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "24px",
            }}
          >
            <div style={{ textAlign: "center", padding: "16px" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>1️⃣</div>
              <h4 style={{ marginBottom: "8px" }}>Create Request</h4>
              <p className="text-secondary text-sm">
                Describe your repair needs and get an instant price estimate
              </p>
            </div>
            <div style={{ textAlign: "center", padding: "16px" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>2️⃣</div>
              <h4 style={{ marginBottom: "8px" }}>Get Matched</h4>
              <p className="text-secondary text-sm">
                Our system finds the best available technician near you
              </p>
            </div>
            <div style={{ textAlign: "center", padding: "16px" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>3️⃣</div>
              <h4 style={{ marginBottom: "8px" }}>Track Progress</h4>
              <p className="text-secondary text-sm">
                Real-time updates on technician ETA and job status
              </p>
            </div>
            <div style={{ textAlign: "center", padding: "16px" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>4️⃣</div>
              <h4 style={{ marginBottom: "8px" }}>Pay & Rate</h4>
              <p className="text-secondary text-sm">
                Secure payment and rate your experience
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ marginTop: "24px" }}>
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Quick Actions</h3>
          </div>
          <div className="card-body">
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "16px",
              }}
            >
              <Link
                to="/customer/new-request"
                className="request-card"
                style={{ textDecoration: "none" }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🔧</div>
                <h4>Plumbing</h4>
                <p className="text-secondary text-sm">Pipes, leaks, fixtures</p>
              </Link>
              <Link
                to="/customer/new-request"
                className="request-card"
                style={{ textDecoration: "none" }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "8px" }}>⚡</div>
                <h4>Electrical</h4>
                <p className="text-secondary text-sm">
                  Wiring, outlets, lights
                </p>
              </Link>
              <Link
                to="/customer/new-request"
                className="request-card"
                style={{ textDecoration: "none" }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "8px" }}>❄️</div>
                <h4>HVAC</h4>
                <p className="text-secondary text-sm">Heating & cooling</p>
              </Link>
              <Link
                to="/customer/new-request"
                className="request-card"
                style={{ textDecoration: "none" }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🏠</div>
                <h4>General</h4>
                <p className="text-secondary text-sm">Other repairs</p>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
