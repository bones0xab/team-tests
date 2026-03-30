import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import Sidebar from "../components/Sidebar";
import PortfolioCard from "../components/PortfolioCard";
import { DashboardSkeleton } from "../components/DashboardSkeleton";
import { useNavigate } from "react-router-dom";

const PortfolioPage: React.FC = () => {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();

  const loadPortfolio = async () => {
    setLoading(true);
    try {
      const data = await api.getPortfolio();
      setItems(data);
    } catch (err: any) {
      setError(err.message || "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPortfolio();
  }, []);

  const handleLogout = async () => {
    await api.logout();
    navigate("/login", { replace: true });
  };

  const totals = items.reduce(
    (acc, curr) => ({
      total: acc.total + curr.total_issues,
      wip: acc.wip + curr.wip_count,
      stale: acc.stale + curr.stale_count,
    }),
    { total: 0, wip: 0, stale: 0 }
  );

  return (
    <div className="app-shell">
      <button
        type="button"
        className="menu-toggle"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle menu"
      >
        Menu
      </button>

      <Sidebar
        open={sidebarOpen}
        projects={[]}
        projectKey={null}
        setProjectKey={() => {}}
        daysBack={30}
        setDaysBack={() => {}}
        onLogout={handleLogout}
      />

      <main className="main-content">
        <header className="page-header fade-in">
          <div className="header-top">
            <div>
              <p className="header-eyebrow">Executive Summary</p>
              <h1 className="header-title">
                Portfolio <span>Intelligence</span>
              </h1>
              <p className="header-sub">
                Aggregated health and risk overview across all active projects.
              </p>
            </div>
            <div className="header-actions">
              <button
                className="btn btn-primary"
                onClick={loadPortfolio}
                disabled={loading}
              >
                {loading ? "Refreshing..." : "Refresh Portfolio"}
              </button>
            </div>
          </div>
        </header>

        {loading && items.length === 0 ? (
          <DashboardSkeleton />
        ) : error ? (
          <div className="error-box">{error}</div>
        ) : (
          <div className="portfolio-content stagger-children">
            <div className="portfolio-summary-grid fade-in">
              <div className="portfolio-summary-card">
                <div className="summary-label">Total Portfolio Issues</div>
                <div className="summary-value">{totals.total}</div>
              </div>
              <div className="portfolio-summary-card">
                <div className="summary-label">Active WIP</div>
                <div className="summary-value">{totals.wip}</div>
              </div>
              <div className={`portfolio-summary-card ${totals.stale > 0 ? "warning" : ""}`}>
                <div className="summary-label">Total Stale Items</div>
                <div className="summary-value">{totals.stale}</div>
              </div>
              <div className="portfolio-summary-card">
                <div className="summary-label">Active Projects</div>
                <div className="summary-value">{items.length}</div>
              </div>
            </div>

            <h2 className="section-label">Project Health Grid</h2>

            <div className="portfolio-grid">
              {items.map((item) => (
                <PortfolioCard key={item.project_key} item={item} />
              ))}
            </div>

            {items.length === 0 && (
              <div className="empty-state">
                <h2>No Projects Found</h2>
                <p>Ensure you have access to Jira projects in your connected instance.</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

export default PortfolioPage;