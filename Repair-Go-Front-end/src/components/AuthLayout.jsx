import { Outlet } from "react-router-dom";

export default function AuthLayout() {
  return (
    <div className="auth-layout">
      <div className="auth-card">
        <div className="auth-logo">
          <h1>
            Repair<span>Go</span>
          </h1>
        </div>
        <Outlet />
      </div>
    </div>
  );
}
