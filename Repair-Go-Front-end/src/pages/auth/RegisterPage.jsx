import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { authAPI } from "../../services/api";

export default function RegisterPage() {
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState("customer");
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    setValue,
  } = useForm();
  const password = watch("password");
  const [locating, setLocating] = useState(false);

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation not supported on this device");
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setValue("latitude", latitude.toFixed(6));
        setValue("longitude", longitude.toFixed(6));
        toast.success("Location captured");
        setLocating(false);
      },
      () => {
        toast.error("Unable to fetch location. Please allow permission.");
        setLocating(false);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 },
    );
  };

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      if (role === "technician") {
        // Register as technician - send skills as array
        await authAPI.registerTechnician({
          name: data.name,
          email: data.email,
          password: data.password,
          skills: [data.specialization], // Send as array
          latitude: parseFloat(data.latitude) || 0,
          longitude: parseFloat(data.longitude) || 0,
          availability: true,
          experience_years: 0,
          workload: 0,
          rating: 0,
          completed_jobs: 0,
        });
      } else {
        // Register as customer
        await authAPI.register({
          name: data.name,
          email: data.email,
          password: data.password,
          role: "customer",
        });
      }

      toast.success("Registration successful! Please login.");
      navigate("/login");
    } catch (error) {
      const errorMsg =
        typeof error.message === "string"
          ? error.message
          : "Registration failed";
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="auth-title">
        <h2>Create Account</h2>
        <p>Join RepairGo today</p>
      </div>

      {/* Role Tabs */}
      <div className="tabs" style={{ marginBottom: "24px" }}>
        <ul className="tabs-list">
          <li
            className={`tab-item ${role === "customer" ? "active" : ""}`}
            onClick={() => setRole("customer")}
          >
            Customer
          </li>
          <li
            className={`tab-item ${role === "technician" ? "active" : ""}`}
            onClick={() => setRole("technician")}
          >
            Technician
          </li>
        </ul>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="form-group">
          <label className="form-label required">Full Name</label>
          <input
            type="text"
            className={`form-input ${errors.name ? "error" : ""}`}
            placeholder="Enter your name"
            {...register("name", { required: "Name is required" })}
          />
          {errors.name && (
            <span className="form-error">{errors.name.message}</span>
          )}
        </div>

        <div className="form-group">
          <label className="form-label required">Email</label>
          <input
            type="email"
            className={`form-input ${errors.email ? "error" : ""}`}
            placeholder="Enter your email"
            {...register("email", {
              required: "Email is required",
              pattern: {
                value: /^\S+@\S+$/i,
                message: "Invalid email address",
              },
            })}
          />
          {errors.email && (
            <span className="form-error">{errors.email.message}</span>
          )}
        </div>

        <div className="form-group">
          <label className="form-label required">Password</label>
          <input
            type="password"
            className={`form-input ${errors.password ? "error" : ""}`}
            placeholder="Create a password"
            {...register("password", {
              required: "Password is required",
              minLength: {
                value: 6,
                message: "Password must be at least 6 characters",
              },
            })}
          />
          {errors.password && (
            <span className="form-error">{errors.password.message}</span>
          )}
        </div>

        <div className="form-group">
          <label className="form-label required">Confirm Password</label>
          <input
            type="password"
            className={`form-input ${errors.confirmPassword ? "error" : ""}`}
            placeholder="Confirm your password"
            {...register("confirmPassword", {
              required: "Please confirm your password",
              validate: (value) =>
                value === password || "Passwords do not match",
            })}
          />
          {errors.confirmPassword && (
            <span className="form-error">{errors.confirmPassword.message}</span>
          )}
        </div>

        {role === "technician" && (
          <>
            <div className="form-group">
              <label className="form-label required">Specialization</label>
              <select
                className={`form-select ${errors.specialization ? "error" : ""}`}
                {...register("specialization", {
                  required: "Specialization is required",
                })}
              >
                <option value="">Select specialization</option>
                <option value="Plumbing">Plumbing</option>
                <option value="Electrical">Electrical</option>
                <option value="HVAC">HVAC</option>
                <option value="Appliance Repair">Appliance Repair</option>
                <option value="Roofing">Roofing</option>
                <option value="Painting">Painting</option>
                <option value="Carpentry">Carpentry</option>
                <option value="Locksmith">Locksmith</option>
              </select>
              {errors.specialization && (
                <span className="form-error">
                  {errors.specialization.message}
                </span>
              )}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "16px",
              }}
            >
              <div className="form-group">
                <label className="form-label">Latitude</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  placeholder="e.g., 40.7128"
                  {...register("latitude")}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Longitude</label>
                <input
                  type="number"
                  step="any"
                  className="form-input"
                  placeholder="e.g., -74.0060"
                  {...register("longitude")}
                />
              </div>
            </div>

            <button
              type="button"
              className="btn btn-outline"
              style={{ marginTop: "12px" }}
              onClick={useMyLocation}
              disabled={locating}
            >
              {locating ? "Capturing location..." : "Use my current location"}
            </button>
          </>
        )}

        <button
          type="submit"
          className="btn btn-primary btn-block btn-lg"
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="loading-spinner sm"></span>
              Creating account...
            </>
          ) : (
            "Create Account"
          )}
        </button>
      </form>

      <div style={{ marginTop: "24px", textAlign: "center" }}>
        <p className="text-secondary">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </>
  );
}
