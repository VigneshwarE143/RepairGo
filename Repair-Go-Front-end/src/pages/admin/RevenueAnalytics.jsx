import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { adminAPI } from "../../services/api";

export default function RevenueAnalytics() {
  const [loading, setLoading] = useState(true);
  const [revenue, setRevenue] = useState({
    total: 0,
    by_month: {},
    by_category: {},
  });
  const [jobs, setJobs] = useState([]);
  const [dateRange, setDateRange] = useState("all");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [revenueRes, jobsRes] = await Promise.all([
        adminAPI.getRevenue().catch(() => ({ data: null })),
        adminAPI.getJobs(),
      ]);

      const allJobs = jobsRes.data || [];
      const completedJobs = allJobs.filter((j) =>
        ["completed", "rated"].includes(j.status),
      );

      // Calculate revenue from jobs if API doesn't return it
      if (revenueRes.data) {
        setRevenue(revenueRes.data);
      } else {
        const total = completedJobs.reduce(
          (sum, j) => sum + (j.estimated_price || 0),
          0,
        );

        // Group by month
        const byMonth = {};
        completedJobs.forEach((job) => {
          const month = new Date(job.created_at).toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
          });
          byMonth[month] = (byMonth[month] || 0) + (job.estimated_price || 0);
        });

        // Group by category
        const byCategory = {};
        completedJobs.forEach((job) => {
          byCategory[job.category] =
            (byCategory[job.category] || 0) + (job.estimated_price || 0);
        });

        setRevenue({ total, by_month: byMonth, by_category: byCategory });
      }

      setJobs(completedJobs);
    } catch (error) {
      toast.error("Failed to load revenue data");
    } finally {
      setLoading(false);
    }
  };

  const monthlyData = Object.entries(revenue.by_month || {})
    .map(([month, amount]) => ({ month, amount }))
    .slice(-6);

  const categoryData = Object.entries(revenue.by_category || {})
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount);

  const maxMonthly = Math.max(...monthlyData.map((d) => d.amount), 1);
  const maxCategory = Math.max(...categoryData.map((d) => d.amount), 1);

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
        <h1>Revenue Analytics</h1>
        <p>Track revenue performance and trends</p>
      </div>

      {/* Summary Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon success">💰</div>
          <div className="stat-content">
            <div className="stat-value">
              ${revenue.total?.toFixed(2) || "0.00"}
            </div>
            <div className="stat-label">Total Revenue</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon primary">📋</div>
          <div className="stat-content">
            <div className="stat-value">{jobs.length}</div>
            <div className="stat-label">Completed Jobs</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon info">📊</div>
          <div className="stat-content">
            <div className="stat-value">
              $
              {jobs.length > 0
                ? (revenue.total / jobs.length).toFixed(2)
                : "0.00"}
            </div>
            <div className="stat-label">Avg per Job</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon warning">📁</div>
          <div className="stat-content">
            <div className="stat-value">{categoryData.length}</div>
            <div className="stat-label">Categories</div>
          </div>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "24px",
          marginTop: "24px",
        }}
      >
        {/* Monthly Revenue Chart */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">📈 Monthly Revenue</h3>
          </div>
          <div className="card-body">
            {monthlyData.length === 0 ? (
              <div className="text-center text-muted py-4">
                No data available
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  gap: "8px",
                  alignItems: "flex-end",
                  height: "200px",
                }}
              >
                {monthlyData.map((item, index) => (
                  <div
                    key={index}
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                    }}
                  >
                    <div
                      style={{
                        width: "100%",
                        height: `${(item.amount / maxMonthly) * 160}px`,
                        background:
                          "linear-gradient(180deg, var(--primary) 0%, var(--primary-light) 100%)",
                        borderRadius: "4px 4px 0 0",
                        minHeight: "10px",
                      }}
                      title={`$${item.amount.toFixed(2)}`}
                    ></div>
                    <div
                      className="text-sm text-muted mt-2"
                      style={{ fontSize: "0.7rem" }}
                    >
                      {item.month}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Revenue by Category */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">📊 Revenue by Category</h3>
          </div>
          <div className="card-body">
            {categoryData.length === 0 ? (
              <div className="text-center text-muted py-4">
                No data available
              </div>
            ) : (
              <div style={{ display: "grid", gap: "16px" }}>
                {categoryData.slice(0, 5).map((item, index) => (
                  <div key={index}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginBottom: "4px",
                      }}
                    >
                      <span style={{ textTransform: "capitalize" }}>
                        {item.category}
                      </span>
                      <strong>${item.amount.toFixed(2)}</strong>
                    </div>
                    <div className="progress">
                      <div
                        className="progress-bar primary"
                        style={{
                          width: `${(item.amount / maxCategory) * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="card" style={{ marginTop: "24px" }}>
        <div className="card-header">
          <h3 className="card-title">💳 Recent Transactions</h3>
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Category</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td
                    colSpan="5"
                    style={{ textAlign: "center", padding: "32px" }}
                  >
                    No transactions found
                  </td>
                </tr>
              ) : (
                jobs.slice(0, 10).map((job) => (
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
                      <strong style={{ color: "var(--success)" }}>
                        ${job.estimated_price?.toFixed(2) || "0.00"}
                      </strong>
                    </td>
                    <td>
                      <span
                        className={`badge ${job.payment_status === "paid" ? "badge-success" : "badge-warning"}`}
                      >
                        {job.payment_status || "completed"}
                      </span>
                    </td>
                    <td>{new Date(job.created_at).toLocaleDateString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
