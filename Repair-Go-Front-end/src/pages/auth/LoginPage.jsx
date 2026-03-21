import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDispatch } from "react-redux";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { authAPI } from "../../services/api";
import { login } from "../../store";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      const response = await authAPI.login(data);

      // Response is already unwrapped by interceptor: { success, message, data }
      const { access_token, role } = response.data;

      if (!access_token) {
        throw new Error("No access token received");
      }

      dispatch(login({ token: access_token, role }));
      localStorage.setItem("token", access_token);
      localStorage.setItem("role", role);
      toast.success("Welcome back!");

      // Navigate based on role
      const routes = {
        admin: "/admin",
        technician: "/technician",
        customer: "/customer",
      };
      window.location.href = routes[role] || "/customer";
    } catch (error) {
      toast.error(error.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="auth-title">
        <h2>Welcome Back</h2>
        <p>Sign in to your account</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
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
            placeholder="Enter your password"
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

        <button
          type="submit"
          className="btn btn-primary btn-block btn-lg"
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="loading-spinner sm"></span>
              Signing in...
            </>
          ) : (
            "Sign In"
          )}
        </button>
      </form>

      <div style={{ marginTop: "24px", textAlign: "center" }}>
        <p className="text-secondary">
          Don't have an account? <Link to="/register">Create one</Link>
        </p>
      </div>
    </>
  );
}
