import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { adminAPI } from "../../services/api";

export default function JobsManagement() {
  const [searchParams] = useSearchParams();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [filter, setFilter] = useState(searchParams.get("status") || "all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getJobs();
      setJobs(response.data || []);
    } catch (error) {
      toast.error("Failed to load jobs");
    } finally {
      setLoading(false);
    }
  };

  const handleAutoAssign = async (jobId) => {
    setActionLoading(true);
    try {
      await adminAPI.assignTechnician(jobId);
      toast.success("Job auto-assigned successfully");
      loadJobs();
    } catch (error) {
      toast.error(error.message || "Failed to auto-assign job");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReassignStale = async () => {
    setActionLoading(true);
    try {
      const response = await adminAPI.reassignStale();
      toast.success(`Reassigned ${response.data?.reassigned || 0} stale jobs`);
      loadJobs();
    } catch (error) {
      toast.error("Failed to reassign stale jobs");
    } finally {
      setActionLoading(false);
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

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job._id?.toLowerCase().includes(search.toLowerCase()) ||
      job.category?.toLowerCase().includes(search.toLowerCase());

    let matchesFilter = true;
    if (filter === "pending") matchesFilter = job.status === "pending";
    else if (filter === "active")
      matchesFilter = ["assigned", "on_the_way", "in_progress"].includes(
        job.status,
      );
    else if (filter === "completed")
      matchesFilter = ["completed", "rated"].includes(job.status);
    else if (filter === "cancelled") matchesFilter = job.status === "cancelled";

    return matchesSearch && matchesFilter;
  });

  const pendingCount = jobs.filter((j) => j.status === "pending").length;
  const activeCount = jobs.filter((j) =>
    ["assigned", "on_the_way", "in_progress"].includes(j.status),
  ).length;

  return (
    <div>
      <div className="page-header">
        <h1>Jobs Management</h1>
        <p>Monitor and manage all service requests</p>
        <div className="page-header-actions">
          <button
            className="btn btn-outline"
            onClick={handleReassignStale}
            disabled={actionLoading}
          >
            🔄 Reassign Stale Jobs
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div style={{ display: "flex", gap: "16px", marginBottom: "24px" }}>
        <div
          className="card"
          style={{ flex: 1, textAlign: "center", padding: "16px" }}
        >
          <div
            style={{
              fontSize: "2rem",
              fontWeight: 700,
              color: "var(--warning)",
            }}
          >
            {pendingCount}
          </div>
          <div className="text-secondary">Pending</div>
        </div>
        <div
          className="card"
          style={{ flex: 1, textAlign: "center", padding: "16px" }}
        >
          <div
            style={{ fontSize: "2rem", fontWeight: 700, color: "var(--info)" }}
          >
            {activeCount}
          </div>
          <div className="text-secondary">Active</div>
        </div>
        <div
          className="card"
          style={{ flex: 1, textAlign: "center", padding: "16px" }}
        >
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>{jobs.length}</div>
          <div className="text-secondary">Total</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: "24px" }}>
        <div className="card-body" style={{ padding: "16px 24px" }}>
          <div
            style={{
              display: "flex",
              gap: "16px",
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <div
              className="form-group"
              style={{ flex: 1, minWidth: "250px", marginBottom: 0 }}
            >
              <input
                type="text"
                className="form-input"
                placeholder="Search by ID or category..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              {["all", "pending", "active", "completed", "cancelled"].map(
                (f) => (
                  <button
                    key={f}
                    className={`btn ${filter === f ? "btn-primary" : "btn-secondary"} btn-sm`}
                    onClick={() => setFilter(f)}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ),
              )}
            </div>
            <button className="btn btn-outline" onClick={loadJobs}>
              🔄 Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      {loading ? (
        <div className="loading-page">
          <div className="loading-spinner lg"></div>
        </div>
      ) : (
        <div className="card">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Category</th>
                  <th>Urgency</th>
                  <th>Status</th>
                  <th>Price</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.length === 0 ? (
                  <tr>
                    <td
                      colSpan="7"
                      style={{ textAlign: "center", padding: "32px" }}
                    >
                      No jobs found
                    </td>
                  </tr>
                ) : (
                  filteredJobs.map((job) => (
                    <tr key={job._id}>
                      <td>
                        <code style={{ fontSize: "0.75rem" }}>
                          {job._id?.substring(0, 8)}...
                        </code>
                      </td>
                      <td style={{ textTransform: "capitalize" }}>
                        {job.category}
                      </td>
                      <td>
                        <span
                          className={`badge ${job.urgency === "high" ? "badge-danger" : job.urgency === "medium" ? "badge-warning" : "badge-secondary"}`}
                        >
                          {job.urgency}
                        </span>
                      </td>
                      <td>{getStatusBadge(job.status)}</td>
                      <td>${job.estimated_price?.toFixed(2) || "0.00"}</td>
                      <td>{new Date(job.created_at).toLocaleDateString()}</td>
                      <td>
                        {job.status === "pending" && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleAutoAssign(job._id)}
                            disabled={actionLoading}
                          >
                            Auto-Assign
                          </button>
                        )}
                        {["completed", "rated"].includes(job.status) && (
                          <span className="text-muted text-sm">Completed</span>
                        )}
                        {["assigned", "on_the_way", "in_progress"].includes(
                          job.status,
                        ) && (
                          <span className="badge badge-info">In Progress</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
