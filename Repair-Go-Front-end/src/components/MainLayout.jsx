import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useSelector, useDispatch } from "react-redux";
import { useEffect, useRef, useState } from "react";
import { logout, addNotification } from "../store";
import { createWebSocket, serviceAPI, technicianAPI } from "../services/api";
import toast from "react-hot-toast";

// Navigation configs for each role
const navConfigs = {
  customer: [
    { path: "/customer", label: "Dashboard", icon: "📊", exact: true },
    { path: "/customer/new-request", label: "New Request", icon: "➕" },
    { path: "/customer/my-requests", label: "My Requests", icon: "📋" },
    { path: "/profile", label: "Profile", icon: "👤" },
  ],
  technician: [
    { path: "/technician", label: "Dashboard", icon: "📊", exact: true },
    { path: "/technician/jobs", label: "My Jobs", icon: "🔧" },
    { path: "/profile", label: "Profile", icon: "👤" },
  ],
  admin: [
    {
      section: "Overview",
      items: [{ path: "/admin", label: "Dashboard", icon: "📊", exact: true }],
    },
    {
      section: "Management",
      items: [
        { path: "/admin/users", label: "Users", icon: "👥" },
        { path: "/admin/technicians", label: "Technicians", icon: "🔧" },
        { path: "/admin/jobs", label: "Jobs", icon: "📋" },
        { path: "/admin/categories", label: "Categories", icon: "🏷️" },
      ],
    },
    {
      section: "Analytics",
      items: [
        { path: "/admin/revenue", label: "Revenue", icon: "💰" },
        { path: "/admin/fraud", label: "Fraud Detection", icon: "🛡️" },
      ],
    },
    {
      section: "System",
      items: [
        { path: "/admin/ml-models", label: "ML Models", icon: "🤖" },
        { path: "/admin/system", label: "System Health", icon: "⚡" },
        { path: "/profile", label: "Profile", icon: "👤" },
      ],
    },
  ],
};

export default function MainLayout() {
  const { role, token } = useSelector((state) => state.auth);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [ws, setWs] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const lastSeenStatusRef = useRef({});

  // WebSocket connection for real-time notifications (optional - fails silently)
  useEffect(() => {
    if (token) {
      try {
        // Extract user ID from token (simple decode)
        const payload = JSON.parse(atob(token.split(".")[1]));
        const userId = payload.sub;

        const websocket = createWebSocket(userId, (data) => {
          if (data.type === "notification") {
            toast(data.message, { icon: "🔔" });
            setNotifications((prev) => [{ id: Date.now(), ...data }, ...prev]);
            dispatch(addNotification(data));
          }
        });

        // Handle WebSocket errors silently
        websocket.onerror = () => {};

        setWs(websocket);

        return () => {
          if (websocket.readyState === WebSocket.OPEN) {
            websocket.close();
          }
        };
      } catch {
        // WebSocket is optional - fail silently
      }
    }
  }, [token, dispatch]);

  // Polling fallback for websocket instability.
  useEffect(() => {
    if (!token || !role) return;

    const interval = setInterval(async () => {
      try {
        if (role === "customer") {
          const response = await serviceAPI.getMyRequests();
          const requests = response.data || [];
          requests.forEach((item) => {
            const current = item.status;
            const previous = lastSeenStatusRef.current[item._id];
            lastSeenStatusRef.current[item._id] = current;
            if (previous && previous !== current) {
              const message = `Request ${item._id?.slice(-6)} status: ${current.replace(/_/g, " ")}`;
              toast(message, { icon: "🔔" });
              const event = {
                type: "notification",
                message,
                related_id: item._id,
              };
              setNotifications((prev) => [
                { id: Date.now(), ...event },
                ...prev,
              ]);
              dispatch(addNotification(event));
            }
          });
        }

        if (role === "technician") {
          const response = await technicianAPI.getPendingJobs();
          const pendingJobs = response.data || [];
          pendingJobs.forEach((job) => {
            const key = `pending:${job._id}`;
            const previouslySeen = lastSeenStatusRef.current[key];
            if (!previouslySeen) {
              const message = `New pending job: ${job.category || "service"}`;
              toast(message, { icon: "🔔" });
              const event = {
                type: "notification",
                message,
                related_id: job._id,
              };
              setNotifications((prev) => [
                { id: Date.now(), ...event },
                ...prev,
              ]);
              dispatch(addNotification(event));
            }
            lastSeenStatusRef.current[key] = true;
          });
        }
      } catch {
        // Polling is best-effort fallback; ignore transient failures.
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [token, role, dispatch]);

  const handleLogout = () => {
    if (ws) ws.close();
    dispatch(logout());
    navigate("/login");
  };

  const renderNavItems = () => {
    const config = navConfigs[role];
    if (!config) return null;

    // Check if admin (has sections)
    if (role === "admin") {
      return config.map((section, idx) => (
        <div key={idx} className="nav-section">
          <div className="nav-section-title">{section.section}</div>
          {section.items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      ));
    }

    // Customer/Technician - flat list
    return (
      <div className="nav-section">
        {config.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.exact}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <span className="nav-item-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>
    );
  };

  return (
    <div className="main-layout">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="sidebar-logo-icon">🔧</div>
            <span>RepairGo</span>
          </div>
        </div>

        <nav className="sidebar-nav">{renderNavItems()}</nav>

        <div className="sidebar-footer">
          <div className="user-menu" onClick={handleLogout}>
            <div className="user-avatar">{role?.charAt(0).toUpperCase()}</div>
            <div className="user-info">
              <div className="user-name">{role}</div>
              <div className="user-role">Click to logout</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Header */}
        <header className="header">
          <div className="header-left">
            <button
              className="btn btn-ghost btn-icon"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              ☰
            </button>
          </div>

          <div className="header-right">
            <div style={{ position: "relative" }}>
              <button
                className="header-icon-btn"
                onClick={() => setShowNotifications(!showNotifications)}
              >
                🔔
                {notifications.length > 0 && <span className="badge" />}
              </button>

              {showNotifications && (
                <div className="dropdown-menu" style={{ minWidth: 280 }}>
                  <div
                    style={{
                      padding: "8px 12px",
                      fontWeight: 600,
                      borderBottom: "1px solid var(--border-color)",
                    }}
                  >
                    Notifications
                  </div>
                  {notifications.length === 0 ? (
                    <div
                      style={{
                        padding: "16px",
                        textAlign: "center",
                        color: "var(--text-muted)",
                      }}
                    >
                      No notifications
                    </div>
                  ) : (
                    notifications.slice(0, 5).map((n) => (
                      <div key={n.id} className="dropdown-item">
                        {n.message}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
