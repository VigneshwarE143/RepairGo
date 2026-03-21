import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { adminAPI, mlAPI } from "../../services/api";

export default function TechniciansManagement() {
  const [technicians, setTechnicians] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [specializationFilter, setSpecializationFilter] = useState("all");
  const [selectedTechnician, setSelectedTechnician] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [reliability, setReliability] = useState(null);

  useEffect(() => {
    loadTechnicians();
  }, []);

  const loadTechnicians = async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getTechnicians();
      setTechnicians(response.data || []);
    } catch (error) {
      toast.error("Failed to load technicians");
    } finally {
      setLoading(false);
    }
  };

  const viewTechnicianDetails = async (technician) => {
    setSelectedTechnician(technician);
    setShowDetailModal(true);

    // Get reliability prediction
    try {
      const res = await mlAPI.predictReliability({
        avg_rating: technician.rating || 4.0,
        cancellation_rate: technician.cancellation_rate || 0.1,
        avg_response_time: 20,
        completed_jobs: technician.completed_jobs || 10,
        current_workload: technician.workload || 0,
        distance_to_customer: 5,
      });
      setReliability(res.data);
    } catch (error) {
      setReliability(null);
    }
  };

  const specializations = [
    ...new Set(technicians.map((t) => t.specialization).filter(Boolean)),
  ];

  const filteredTechnicians = technicians.filter((tech) => {
    const matchesSearch =
      tech.email?.toLowerCase().includes(search.toLowerCase()) ||
      tech.name?.toLowerCase().includes(search.toLowerCase());

    const matchesSpecialization =
      specializationFilter === "all" ||
      tech.specialization === specializationFilter;

    return matchesSearch && matchesSpecialization;
  });

  const getStatusBadge = (tech) => {
    if (tech.is_available === false) {
      return <span className="badge badge-secondary">Unavailable</span>;
    }
    if (tech.current_workload > 3) {
      return <span className="badge badge-warning">Busy</span>;
    }
    return <span className="badge badge-success">Available</span>;
  };

  return (
    <div>
      <div className="page-header">
        <h1>Technicians Management</h1>
        <p>View and manage technician accounts and performance</p>
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
                placeholder="Search by name or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <select
                className="form-select"
                value={specializationFilter}
                onChange={(e) => setSpecializationFilter(e.target.value)}
              >
                <option value="all">All Specializations</option>
                {specializations.map((spec) => (
                  <option key={spec} value={spec}>
                    {spec.charAt(0).toUpperCase() + spec.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <button className="btn btn-outline" onClick={loadTechnicians}>
              🔄 Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Technicians Table */}
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
                  <th>Technician</th>
                  <th>Specialization</th>
                  <th>Rating</th>
                  <th>Completed</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTechnicians.length === 0 ? (
                  <tr>
                    <td
                      colSpan="6"
                      style={{ textAlign: "center", padding: "32px" }}
                    >
                      No technicians found
                    </td>
                  </tr>
                ) : (
                  filteredTechnicians.map((tech) => (
                    <tr key={tech._id}>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "12px",
                          }}
                        >
                          <div
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: "50%",
                              background: "var(--info-light)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontWeight: 600,
                              color: "var(--info)",
                            }}
                          >
                            {tech.name?.charAt(0).toUpperCase() || "T"}
                          </div>
                          <div>
                            <div className="font-medium">
                              {tech.name || "Unknown"}
                            </div>
                            <div className="text-sm text-muted">
                              {tech.email}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td style={{ textTransform: "capitalize" }}>
                        {tech.specialization || "—"}
                      </td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          ⭐ {tech.avg_rating?.toFixed(1) || "N/A"}
                        </div>
                      </td>
                      <td>{tech.completed_jobs || 0} jobs</td>
                      <td>{getStatusBadge(tech)}</td>
                      <td>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => viewTechnicianDetails(tech)}
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedTechnician && (
        <div
          className="modal-overlay"
          onClick={() => setShowDetailModal(false)}
        >
          <div
            className="modal"
            style={{ maxWidth: "600px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3 className="modal-title">Technician Details</h3>
              <button
                className="modal-close"
                onClick={() => setShowDetailModal(false)}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div
                style={{ display: "flex", gap: "24px", marginBottom: "24px" }}
              >
                <div
                  style={{
                    width: 80,
                    height: 80,
                    borderRadius: "50%",
                    background: "var(--info-light)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "2rem",
                    fontWeight: 600,
                    color: "var(--info)",
                  }}
                >
                  {selectedTechnician.name?.charAt(0).toUpperCase() || "T"}
                </div>
                <div>
                  <h2 style={{ marginBottom: "4px" }}>
                    {selectedTechnician.name || "Unknown"}
                  </h2>
                  <p className="text-muted">{selectedTechnician.email}</p>
                  <span
                    className="badge badge-info"
                    style={{ marginTop: "8px", textTransform: "capitalize" }}
                  >
                    {selectedTechnician.specialization || "General"}
                  </span>
                </div>
              </div>

              <div className="stats-grid" style={{ marginBottom: "24px" }}>
                <div className="stat-card">
                  <div className="stat-content">
                    <div className="stat-value">
                      ⭐ {selectedTechnician.avg_rating?.toFixed(1) || "N/A"}
                    </div>
                    <div className="stat-label">Rating</div>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-content">
                    <div className="stat-value">
                      {selectedTechnician.completed_jobs || 0}
                    </div>
                    <div className="stat-label">Completed</div>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-content">
                    <div className="stat-value">
                      {selectedTechnician.current_workload || 0}
                    </div>
                    <div className="stat-label">Current Jobs</div>
                  </div>
                </div>
              </div>

              {/* Reliability Prediction */}
              {reliability && (
                <div className="card" style={{ background: "var(--gray-50)" }}>
                  <div className="card-header">
                    <h4 className="card-title">🤖 ML Reliability Prediction</h4>
                  </div>
                  <div className="card-body">
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div className="text-secondary text-sm">
                          Success Probability
                        </div>
                        <div
                          style={{
                            fontSize: "1.5rem",
                            fontWeight: 700,
                            color: "var(--success)",
                          }}
                        >
                          {(reliability.success_probability * 100).toFixed(0)}%
                        </div>
                      </div>
                      <span className="badge badge-info">
                        {reliability.prediction_source}
                      </span>
                    </div>
                    <div className="progress mt-3">
                      <div
                        className="progress-bar success"
                        style={{
                          width: `${reliability.success_probability * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}

              {/* Performance Metrics */}
              <div style={{ marginTop: "24px" }}>
                <h4 style={{ marginBottom: "16px" }}>Performance Metrics</h4>
                <div style={{ display: "grid", gap: "12px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "12px",
                      background: "var(--gray-50)",
                      borderRadius: "8px",
                    }}
                  >
                    <span>Cancellation Rate</span>
                    <strong>
                      {(
                        (selectedTechnician.cancellation_rate || 0) * 100
                      ).toFixed(1)}
                      %
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
                    <span>Avg Response Time</span>
                    <strong>
                      {selectedTechnician.avg_response_time || "N/A"} mins
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
                    <span>Account Created</span>
                    <strong>
                      {selectedTechnician.created_at
                        ? new Date(
                            selectedTechnician.created_at,
                          ).toLocaleDateString()
                        : "N/A"}
                    </strong>
                  </div>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowDetailModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
