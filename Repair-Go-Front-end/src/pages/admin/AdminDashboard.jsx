import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { adminAPI, mlAPI } from "../../services/api";

export default function AdminDashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalTechnicians: 0,
    totalJobs: 0,
    totalRevenue: 0,
    pendingJobs: 0,
    activeJobs: 0,
    completedJobs: 0,
  });
  const [demandForecast, setDemandForecast] = useState(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [usersRes, techniciansRes, jobsRes, revenueRes] = await Promise.all(
        [
          adminAPI.getUsers(),
          adminAPI.getTechnicians(),
          adminAPI.getJobs(),
          adminAPI.getRevenue().catch(() => ({ data: { total: 0 } })),
        ],
      );

      const jobs = jobsRes.data || [];

      setStats({
        totalUsers: usersRes.data?.length || 0,
        totalTechnicians: techniciansRes.data?.length || 0,
        totalJobs: jobs.length,
        totalRevenue:
          revenueRes.data?.total_revenue ||
          jobs.reduce((sum, j) => sum + (j.estimated_price || 0), 0),
        pendingJobs: jobs.filter((j) => j.status === "pending").length,
        activeJobs: jobs.filter((j) =>
          ["assigned", "on_the_way", "in_progress"].includes(j.status),
        ).length,
        completedJobs: jobs.filter((j) =>
          ["completed", "rated"].includes(j.status),
        ).length,
      });

      // Get demand forecast
      try {
        const demandRes = await mlAPI.predictDemand({
          target_time: new Date().toISOString(),
          use_cache: true,
        });
        setDemandForecast(demandRes.data);
      } catch {
        // Demand forecast unavailable
      }
    } catch (error) {
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

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
        <h1>Admin Dashboard</h1>
        <p>Overview of system performance and metrics</p>
      </div>

      {/* Main Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon primary">👥</div>
          <div className="stat-content">
            <div className="stat-value">{stats.totalUsers}</div>
            <div className="stat-label">Total Users</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon info">🔧</div>
          <div className="stat-content">
            <div className="stat-value">{stats.totalTechnicians}</div>
            <div className="stat-label">Technicians</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon warning">📋</div>
          <div className="stat-content">
            <div className="stat-value">{stats.totalJobs}</div>
            <div className="stat-label">Total Jobs</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon success">💰</div>
          <div className="stat-content">
            <div className="stat-value">${stats.totalRevenue.toFixed(0)}</div>
            <div className="stat-label">Total Revenue</div>
          </div>
        </div>
      </div>

      {/* Job Status Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "16px",
          marginTop: "24px",
        }}
      >
        <div className="card" style={{ textAlign: "center" }}>
          <div className="card-body">
            <div
              style={{
                fontSize: "2.5rem",
                fontWeight: 700,
                color: "var(--warning)",
              }}
            >
              {stats.pendingJobs}
            </div>
            <div className="text-secondary">Pending Jobs</div>
            <Link
              to="/admin/jobs?status=pending"
              className="btn btn-ghost btn-sm mt-3"
            >
              View →
            </Link>
          </div>
        </div>

        <div className="card" style={{ textAlign: "center" }}>
          <div className="card-body">
            <div
              style={{
                fontSize: "2.5rem",
                fontWeight: 700,
                color: "var(--info)",
              }}
            >
              {stats.activeJobs}
            </div>
            <div className="text-secondary">Active Jobs</div>
            <Link
              to="/admin/jobs?status=active"
              className="btn btn-ghost btn-sm mt-3"
            >
              View →
            </Link>
          </div>
        </div>

        <div className="card" style={{ textAlign: "center" }}>
          <div className="card-body">
            <div
              style={{
                fontSize: "2.5rem",
                fontWeight: 700,
                color: "var(--success)",
              }}
            >
              {stats.completedJobs}
            </div>
            <div className="text-secondary">Completed</div>
            <Link
              to="/admin/jobs?status=completed"
              className="btn btn-ghost btn-sm mt-3"
            >
              View →
            </Link>
          </div>
        </div>
      </div>

      {/* Demand Forecast & Quick Actions */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "24px",
          marginTop: "24px",
        }}
      >
        {/* Demand Forecast */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">📊 Demand Forecast</h3>
          </div>
          <div className="card-body">
            {demandForecast ? (
              <div>
                <div className="alert alert-info">
                  <span className="alert-icon">🔮</span>
                  <div className="alert-content">
                    <strong>Predicted Demand</strong>
                    <p>
                      Expected {demandForecast.predicted_demand || "moderate"}{" "}
                      demand for plumbing services
                    </p>
                  </div>
                </div>
                <div style={{ marginTop: "16px" }}>
                  <div className="text-secondary text-sm">Confidence Score</div>
                  <div className="progress mt-2">
                    <div
                      className="progress-bar success"
                      style={{
                        width: `${(demandForecast.confidence || 0.75) * 100}%`,
                      }}
                    ></div>
                  </div>
                  <span className="text-sm">
                    {((demandForecast.confidence || 0.75) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-muted text-center py-4">
                <p>Demand forecasting unavailable</p>
                <Link
                  to="/admin/ml-models"
                  className="btn btn-ghost btn-sm mt-2"
                >
                  Configure ML Models
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">⚡ Quick Actions</h3>
          </div>
          <div className="card-body">
            <div style={{ display: "grid", gap: "12px" }}>
              <Link to="/admin/jobs" className="btn btn-outline btn-block">
                📋 Manage Jobs
              </Link>
              <Link
                to="/admin/technicians"
                className="btn btn-outline btn-block"
              >
                🔧 Manage Technicians
              </Link>
              <Link to="/admin/fraud" className="btn btn-outline btn-block">
                🔍 Fraud Detection
              </Link>
              <Link to="/admin/system" className="btn btn-outline btn-block">
                ⚙️ System Health
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* System Alerts */}
      <div className="card" style={{ marginTop: "24px" }}>
        <div className="card-header">
          <h3 className="card-title">🔔 System Alerts</h3>
        </div>
        <div className="card-body">
          {stats.pendingJobs > 5 ? (
            <div className="alert alert-warning">
              <span className="alert-icon">⚠️</span>
              <div className="alert-content">
                <strong>High Pending Jobs</strong>
                <p>
                  There are {stats.pendingJobs} pending jobs. Consider
                  auto-assigning.
                </p>
              </div>
            </div>
          ) : (
            <div className="alert alert-success">
              <span className="alert-icon">✅</span>
              <div className="alert-content">
                <strong>All Systems Normal</strong>
                <p>No critical alerts at this time.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
