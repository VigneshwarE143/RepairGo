import { Routes, Route, Navigate } from "react-router-dom";
import { useSelector } from "react-redux";

// Layouts
import MainLayout from "./components/MainLayout";
import AuthLayout from "./components/AuthLayout";

// Auth Pages
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";

// Customer Pages
import CustomerDashboard from "./pages/customer/CustomerDashboard";
import NewRequest from "./pages/customer/NewRequest";
import MyRequests from "./pages/customer/MyRequests";
import RequestDetails from "./pages/customer/RequestDetails";

// Technician Pages
import TechnicianDashboard from "./pages/technician/TechnicianDashboard";
import TechnicianJobs from "./pages/technician/TechnicianJobs";
import JobDetails from "./pages/technician/JobDetails";

// Admin Pages
import AdminDashboard from "./pages/admin/AdminDashboard";
import UsersManagement from "./pages/admin/UsersManagement";
import TechniciansManagement from "./pages/admin/TechniciansManagement";
import JobsManagement from "./pages/admin/JobsManagement";
import RevenueAnalytics from "./pages/admin/RevenueAnalytics";
import CategoriesManagement from "./pages/admin/CategoriesManagement";
import FraudManagement from "./pages/admin/FraudManagement";
import MLModels from "./pages/admin/MLModels";
import SystemHealth from "./pages/admin/SystemHealth";

// Protected Route Component
function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, role } = useSelector((state) => state.auth);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(role)) {
    const defaultRoutes = {
      admin: "/admin",
      technician: "/technician",
      customer: "/customer",
    };
    return <Navigate to={defaultRoutes[role] || "/login"} replace />;
  }

  return children;
}

// Public Route - redirect if authenticated
function PublicRoute({ children }) {
  const { isAuthenticated, role } = useSelector((state) => state.auth);

  if (isAuthenticated) {
    const routes = {
      admin: "/admin",
      technician: "/technician",
      customer: "/customer",
    };
    return <Navigate to={routes[role] || "/customer"} replace />;
  }

  return children;
}

export default function App() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route element={<AuthLayout />}>
        <Route
          path="/login"
          element={
            <PublicRoute>
              <LoginPage />
            </PublicRoute>
          }
        />
        <Route
          path="/register"
          element={
            <PublicRoute>
              <RegisterPage />
            </PublicRoute>
          }
        />
      </Route>

      {/* Customer Routes */}
      <Route
        path="/customer"
        element={
          <ProtectedRoute allowedRoles={["customer"]}>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<CustomerDashboard />} />
        <Route path="new-request" element={<NewRequest />} />
        <Route path="my-requests" element={<MyRequests />} />
        <Route path="request/:id" element={<RequestDetails />} />
      </Route>

      {/* Technician Routes */}
      <Route
        path="/technician"
        element={
          <ProtectedRoute allowedRoles={["technician"]}>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<TechnicianDashboard />} />
        <Route path="jobs" element={<TechnicianJobs />} />
        <Route path="job/:id" element={<JobDetails />} />
      </Route>

      {/* Admin Routes */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="users" element={<UsersManagement />} />
        <Route path="technicians" element={<TechniciansManagement />} />
        <Route path="jobs" element={<JobsManagement />} />
        <Route path="revenue" element={<RevenueAnalytics />} />
        <Route path="categories" element={<CategoriesManagement />} />
        <Route path="fraud" element={<FraudManagement />} />
        <Route path="ml-models" element={<MLModels />} />
        <Route path="system" element={<SystemHealth />} />
      </Route>

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
