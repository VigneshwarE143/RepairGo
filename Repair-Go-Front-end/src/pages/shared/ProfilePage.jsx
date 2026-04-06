import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { profileAPI } from "../../services/api";

const buildFormData = (data = {}) => ({
  name: data.name || "",
  email: data.email || "",
  phone: data.phone || "",
  address: data.address || "",
  skills: Array.isArray(data.skills) ? data.skills.join(", ") : "",
  upi_id: data.upi_id || "",
  experience_years: data.experience_years ?? "",
});

export default function ProfilePage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(buildFormData());
  const [initialForm, setInitialForm] = useState(buildFormData());
  const [isEditing, setIsEditing] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const response = await profileAPI.getProfile();
      const data = response.data || {};
      const nextForm = buildFormData(data);
      setProfile(data);
      setForm(nextForm);
      setInitialForm(nextForm);
    } catch (error) {
      toast.error(error.message || "Failed to load profile");
    } finally {
      setLoading(false);
    }
  };

  const updateField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const cancelEditing = () => {
    setForm(initialForm);
    setCurrentPassword("");
    setShowPassword(false);
    setIsEditing(false);
  };

  const hasChanges =
    JSON.stringify(form) !== JSON.stringify(initialForm);

  const handleSave = async () => {
    if (!hasChanges) {
      toast("No changes to save");
      return;
    }

    if (!currentPassword.trim()) {
      toast.error("Enter your current password to save changes");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: form.name?.trim(),
        phone: form.phone?.trim(),
        current_password: currentPassword,
      };

      if (profile?.role === "technician") {
        payload.skills = form.skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        const upi = form.upi_id?.trim();
        if (upi) {
          if (!upi.includes("@")) {
            throw new Error("UPI ID must contain '@'");
          }
          payload.upi_id = upi;
        }
        const experience = Number(form.experience_years || 0);
        if (Number.isNaN(experience) || experience < 0) {
          throw new Error("Experience must be a valid non-negative number");
        }
        payload.experience_years = experience;
      } else {
        payload.address = form.address?.trim();
      }

      await profileAPI.updateProfile(payload);
      toast.success("Profile updated");
      setCurrentPassword("");
      setShowPassword(false);
      setIsEditing(false);
      loadProfile();
    } catch (error) {
      toast.error(error.message || "Failed to update profile");
    } finally {
      setSaving(false);
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
    <div className="profile-page">
      <div className="page-header">
        <h1>Profile</h1>
        <p>Review account details and securely update your information.</p>
      </div>

      <div className="profile-layout">
        <div className="card profile-summary-card">
          <div className="card-body">
            <div className="profile-avatar">
              {(profile?.name || "U").trim().charAt(0).toUpperCase()}
            </div>
            <h3>{profile?.name || "Unknown User"}</h3>
            <p className="text-secondary">{profile?.email || "-"}</p>

            <div className="profile-role-badge">
              <span className="badge badge-primary">
                {(profile?.role || "user").toUpperCase()}
              </span>
            </div>

            <div className="profile-meta-list">
              <div className="profile-meta-item">
                <span>Phone</span>
                <strong>{profile?.phone || "Not set"}</strong>
              </div>
              {profile?.role === "technician" ? (
                <>
                  <div className="profile-meta-item">
                    <span>Experience</span>
                    <strong>{profile?.experience_years || 0} years</strong>
                  </div>
                  <div className="profile-meta-item">
                    <span>UPI</span>
                    <strong>{profile?.upi_id || "Not set"}</strong>
                  </div>
                </>
              ) : (
                <div className="profile-meta-item">
                  <span>Address</span>
                  <strong>{profile?.address || "Not set"}</strong>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="card profile-form-card">
          <div className="card-header">
            <h3 className="card-title">
              {profile?.role === "technician"
                ? "Technician Details"
                : "Account Details"}
            </h3>

            <div className="btn-group">
              {isEditing ? (
                <>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={cancelEditing}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                  >
                    {saving ? "Saving..." : "Save Changes"}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="btn btn-outline-primary"
                  onClick={() => setIsEditing(true)}
                >
                  Edit Profile
                </button>
              )}
            </div>
          </div>

          <div className="card-body">
            <div className="profile-form-grid">
              <label className="form-group">
                <span className="form-label">Name</span>
                <input
                  className="form-input"
                  value={form.name || ""}
                  onChange={(e) => updateField("name", e.target.value)}
                  disabled={!isEditing}
                />
              </label>

              <label className="form-group">
                <span className="form-label">Email</span>
                <input className="form-input" value={form.email || ""} disabled />
              </label>

              <label className="form-group">
                <span className="form-label">Phone</span>
                <input
                  className="form-input"
                  value={form.phone || ""}
                  onChange={(e) => updateField("phone", e.target.value)}
                  disabled={!isEditing}
                />
              </label>

              {profile?.role === "technician" ? (
                <>
                  <label className="form-group">
                    <span className="form-label">Skills (comma separated)</span>
                    <input
                      className="form-input"
                      value={form.skills || ""}
                      onChange={(e) => updateField("skills", e.target.value)}
                      disabled={!isEditing}
                    />
                  </label>

                  <label className="form-group">
                    <span className="form-label">UPI ID</span>
                    <input
                      className="form-input"
                      value={form.upi_id || ""}
                      onChange={(e) => updateField("upi_id", e.target.value)}
                      disabled={!isEditing}
                    />
                  </label>

                  <label className="form-group">
                    <span className="form-label">Experience (years)</span>
                    <input
                      type="number"
                      min="0"
                      className="form-input"
                      value={form.experience_years}
                      onChange={(e) =>
                        updateField("experience_years", e.target.value)
                      }
                      disabled={!isEditing}
                    />
                  </label>
                </>
              ) : (
                <label className="form-group profile-form-span-2">
                  <span className="form-label">Address</span>
                  <textarea
                    className="form-textarea"
                    rows="3"
                    value={form.address || ""}
                    onChange={(e) => updateField("address", e.target.value)}
                    disabled={!isEditing}
                  />
                </label>
              )}
            </div>

            {isEditing && (
              <div className="profile-security-box">
                <h4>Security confirmation</h4>
                <p className="text-secondary text-sm">
                  Enter your current password to confirm profile changes.
                </p>

                <label className="form-group" style={{ marginBottom: 0 }}>
                  <span className="form-label">Current Password</span>
                  <div className="profile-password-row">
                    <input
                      type={showPassword ? "text" : "password"}
                      className="form-input"
                      placeholder="Enter current password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowPassword((prev) => !prev)}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </label>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
