import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { technicianAPI } from "../../services/api";

export default function TechnicianDashboard() {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [locationUpdating, setLocationUpdating] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // Get technician profile
      const profileRes = await technicianAPI.getProfile();
      setProfile(profileRes.data);

      // Get jobs
      const jobsRes = await technicianAPI.getMyJobs();
      // Filter to active jobs only
      const activeJobs = (jobsRes.data || []).filter((j) =>
        ["assigned", "on_the_way", "in_progress"].includes(j.status),
      );
      setJobs(activeJobs.slice(0, 5));
    } catch {
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  const updateLocation = async () => {
    setLocationUpdating(true);
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          try {
            await technicianAPI.updateLocation({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
            });
            toast.success("Location updated successfully!");
          } catch (error) {
            toast.error("Failed to update location");
          } finally {
            setLocationUpdating(false);
          }
        },
        (error) => {
          toast.error("Could not get location");
          setLocationUpdating(false);
        },
      );
    } else {
      toast.error("Geolocation not supported");
      setLocationUpdating(false);
    }
  };

  const getStatusBadge = (status) => {
    const classes = {
      assigned: "badge-assigned",
      on_the_way: "badge-info",
      in_progress: "badge-in-progress",
    };
    return (
      <span className={`badge ${classes[status] || "badge-secondary"}`}>
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

  return (
    <div>
      <div className="page-header">
        <h1>Technician Dashboard</h1>
        <p>Manage your jobs and availability</p>
        <div className="page-header-actions">
          <button
            className="btn btn-outline"
            onClick={updateLocation}
            disabled={locationUpdating}
          >
            {locationUpdating ? (
              <>
                <span className="loading-spinner sm"></span>
                Updating...
              </>
            ) : (
              "📍 Update Location"
            )}
          </button>
          <Link to="/technician/jobs" className="btn btn-primary">
            View All Jobs
          </Link>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon primary">📋</div>
          <div className="stat-content">
            <div className="stat-value">{jobs.length}</div>
            <div className="stat-label">Active Jobs</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon warning">⭐</div>
          <div className="stat-content">
            <div className="stat-value">
              {profile?.rating?.toFixed(1) || "0.0"}
            </div>
            <div className="stat-label">Average Rating</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon info">✓</div>
          <div className="stat-content">
            <div className="stat-value">{profile?.completed_jobs || 0}</div>
            <div className="stat-label">Completed Jobs</div>
          </div>
        </div>
      </div>

      {/* Active Jobs */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Active Jobs</h3>
          <Link to="/technician/jobs" className="btn btn-ghost btn-sm">
            View All →
          </Link>
        </div>
        <div className="card-body">
          {jobs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <h3>No Active Jobs</h3>
              <p>You don't have any active jobs at the moment.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gap: "16px" }}>
              {jobs.map((job) => (
                <div key={job._id} className="request-card">
                  <div className="request-header">
                    <div>
                      <span className="request-category">{job.category}</span>
                      <span
                        className="badge badge-secondary"
                        style={{
                          marginLeft: "8px",
                          textTransform: "capitalize",
                        }}
                      >
                        {job.urgency}
                      </span>
                    </div>
                    {getStatusBadge(job.status)}
                  </div>

                  <div className="request-meta">
                    <span className="request-meta-item">
                      📅 {new Date(job.created_at).toLocaleDateString()}
                    </span>
                    {job.eta_minutes && (
                      <span className="request-meta-item">
                        ⏱️ ETA: {job.eta_minutes} mins
                      </span>
                    )}
                  </div>

                  <div className="request-footer">
                    <span className="request-price">
                      ${job.estimated_price?.toFixed(2) || "0.00"}
                    </span>
                    <Link
                      to={`/technician/job/${job._id}`}
                      className="btn btn-primary btn-sm"
                    >
                      Manage Job →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Tips */}
      <div className="card" style={{ marginTop: "24px" }}>
        <div className="card-header">
          <h3 className="card-title">Tips for Success</h3>
        </div>
        <div className="card-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "16px",
            }}
          >
            <div className="alert alert-success">
              <span className="alert-icon">✅</span>
              <div className="alert-content">
                <strong>Keep Location Updated</strong>
                <p className="text-sm">Helps with accurate job assignments</p>
              </div>
            </div>
            <div className="alert alert-info">
              <span className="alert-icon">⏰</span>
              <div className="alert-content">
                <strong>Respond Quickly</strong>
                <p className="text-sm">Fast response improves your score</p>
              </div>
            </div>
            <div className="alert alert-warning">
              <span className="alert-icon">⭐</span>
              <div className="alert-content">
                <strong>Maintain Quality</strong>
                <p className="text-sm">Good ratings mean more jobs</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
