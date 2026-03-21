import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { adminAPI } from "../../services/api";

export default function UsersManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showDeletedToggle, setShowDeletedToggle] = useState(false);
  const [deleteModal, setDeleteModal] = useState({
    show: false,
    user: null,
    permanent: false,
  });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getUsers();
      setUsers(response.data || []);
    } catch (error) {
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    const { user } = deleteModal;
    try {
      await adminAPI.deactivateUser(user._id);
      toast.success("User deactivated");
      setDeleteModal({ show: false, user: null, permanent: false });
      loadUsers();
    } catch (error) {
      toast.error("Failed to deactivate user");
    }
  };

  const handleRestore = async (userId) => {
    try {
      await adminAPI.reactivateUser(userId);
      toast.success("User reactivated");
      loadUsers();
    } catch (error) {
      toast.error("Failed to reactivate user");
    }
  };

  const filteredUsers = users.filter((user) => {
    const matchesSearch =
      user.email?.toLowerCase().includes(search.toLowerCase()) ||
      user.name?.toLowerCase().includes(search.toLowerCase());

    if (!showDeletedToggle) {
      return matchesSearch && !user.is_deleted;
    }
    return matchesSearch;
  });

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div>
      <div className="page-header">
        <h1>Users Management</h1>
        <p>View and manage customer accounts</p>
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
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={showDeletedToggle}
                onChange={(e) => setShowDeletedToggle(e.target.checked)}
              />
              Show deleted users
            </label>
            <button className="btn btn-outline" onClick={loadUsers}>
              🔄 Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Users Table */}
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
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Registered</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td
                      colSpan="6"
                      style={{ textAlign: "center", padding: "32px" }}
                    >
                      No users found
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((user) => (
                    <tr
                      key={user._id}
                      style={{ opacity: user.is_deleted ? 0.6 : 1 }}
                    >
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
                              background: "var(--primary-light)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontWeight: 600,
                              color: "var(--primary)",
                            }}
                          >
                            {user.name?.charAt(0).toUpperCase() || "U"}
                          </div>
                          {user.name || "Unknown"}
                        </div>
                      </td>
                      <td>{user.email}</td>
                      <td>
                        <span
                          className="badge badge-secondary"
                          style={{ textTransform: "capitalize" }}
                        >
                          {user.role}
                        </span>
                      </td>
                      <td>{formatDate(user.created_at)}</td>
                      <td>
                        {user.is_deleted ? (
                          <span className="badge badge-danger">Deleted</span>
                        ) : (
                          <span className="badge badge-success">Active</span>
                        )}
                      </td>
                      <td>
                        {user.is_deleted ? (
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => handleRestore(user._id)}
                          >
                            Restore
                          </button>
                        ) : (
                          <div className="dropdown">
                            <button className="btn btn-ghost btn-sm dropdown-toggle">
                              Actions ▾
                            </button>
                            <div className="dropdown-content">
                              <button
                                className="dropdown-item"
                                onClick={() =>
                                  setDeleteModal({
                                    show: true,
                                    user,
                                    permanent: false,
                                  })
                                }
                              >
                                🗑️ Soft Delete
                              </button>
                              <button
                                className="dropdown-item"
                                style={{ color: "var(--danger)" }}
                                onClick={() =>
                                  setDeleteModal({
                                    show: true,
                                    user,
                                    permanent: true,
                                  })
                                }
                              >
                                ⛔ Permanent Delete
                              </button>
                            </div>
                          </div>
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

      {/* Delete Modal */}
      {deleteModal.show && (
        <div
          className="modal-overlay"
          onClick={() =>
            setDeleteModal({ show: false, user: null, permanent: false })
          }
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {deleteModal.permanent
                  ? "⛔ Permanent Delete"
                  : "🗑️ Soft Delete"}
              </h3>
              <button
                className="modal-close"
                onClick={() =>
                  setDeleteModal({ show: false, user: null, permanent: false })
                }
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              {deleteModal.permanent ? (
                <div className="alert alert-danger">
                  <span className="alert-icon">⚠️</span>
                  <div className="alert-content">
                    <strong>This action cannot be undone!</strong>
                    <p>
                      Permanently deleting this user will remove all their data.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="alert alert-warning">
                  <span className="alert-icon">ℹ️</span>
                  <div className="alert-content">
                    <strong>Soft Delete</strong>
                    <p>
                      The user will be deactivated but can be restored later.
                    </p>
                  </div>
                </div>
              )}
              <p style={{ marginTop: "16px" }}>
                Are you sure you want to delete{" "}
                <strong>{deleteModal.user?.email}</strong>?
              </p>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() =>
                  setDeleteModal({ show: false, user: null, permanent: false })
                }
              >
                Cancel
              </button>
              <button className="btn btn-danger" onClick={handleDelete}>
                {deleteModal.permanent ? "Delete Permanently" : "Soft Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
