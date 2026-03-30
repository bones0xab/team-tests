import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, clearToken, getToken, hasPermission, type CurrentUser } from "./api/client";
import HealthBanner from "./components/HealthBanner";
import KpiGrid from "./components/KpiGrid";
import PaginationControls from "./components/PaginationControls";
import Sidebar from "./components/Sidebar";
import {
  DashboardSkeleton,
  LazyChartsFallback,
  LazyTableFallback,
} from "./components/DashboardSkeleton";
import { useAnalysis } from "./hooks/useAnalysis";
import { useWebSocket, WebSocketContext } from "./hooks/useWebSocket";
const Login = lazy(() => import("./pages/LoginPage"));
const Register = lazy(() => import("./pages/RegisterPage"));
const PortfolioPage = lazy(() => import("./pages/PortfolioPage"));
const AIPage = lazy(() => import("./pages/AIPage"));
const JiraExplorerPage = lazy(() => import("./pages/JiraExplorerPage"));
const TeamScorecardPage = lazy(() => import("./pages/TeamScorecardPage"));
const ManageUsersPage = lazy(() => import("./pages/ManageUsersPage"));
const AdminChoicePage = lazy(() => import("./pages/AdminChoicePage"));

const Charts = lazy(() => import("./components/Charts"));
const IssueTable = lazy(() => import("./components/IssueTable"));
const ExportButtons = lazy(() => import("./components/ExportButtons"));

const LoadingBlock: React.FC<{ label: string }> = ({ label }) => (
  <div className="spinner-wrap">
    <div className="spinner" />
    {label}
  </div>
);

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = getToken();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const PermissionRoute = ({
  children,
  loading,
  user,
  permission,
}: {
  children: React.ReactNode;
  loading: boolean;
  user: CurrentUser | null;
  permission: string;
}) => {
  if (loading) {
    return <LoadingBlock label="Loading user permissions..." />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!hasPermission(user, permission)) {
    return (
      <div className="empty-state">
        <h2>Access Denied</h2>
        <p>You are missing required permission: {permission}</p>
      </div>
    );
  }

  return <>{children}</>;
};

const RootRedirect = ({ loading, user }: { loading: boolean; user: CurrentUser | null }) => {
  if (loading) return <LoadingBlock label="Loading user profile..." />;

  if (!user) return <Navigate to="/login" replace />;

  if (hasPermission(user, "user:manage")) {
    return <Navigate to="/admin" replace />;
  }

  if (hasPermission(user, "dashboard:view")) {
    return <Navigate to="/portfolio" replace />;
  }

  return (
    <div className="empty-state">
      <h2>No Access Configured</h2>
      <p>Your account has no assigned application permissions.</p>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projectKey, setProjectKey] = useState<string | null>(null);
  const [daysBack, setDaysBack] = useState(30);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const initializedRef = useRef(false);
  const { data, loading, isRefreshing, error, refresh } = useAnalysis(
    projectKey,
    daysBack,
    page,
    pageSize
  );

  // One-time initialisation: pick the first project when the list first lands.
  useEffect(() => {
    if (!initializedRef.current && data?.projects?.length) {
      const firstKey = data.projects[0]?.identity?.project_key;
      if (firstKey) {
        initializedRef.current = true;
        setProjectKey(firstKey);
      }
    }
  }, [data]);
  // Reset to page 1 whenever the user switches project or time range so we
  // never request a page that doesn't exist in the new dataset.
  const handleSetProjectKey = (key: string) => {
    setPage(1);
    setProjectKey(key);
  };

  const handleSetDaysBack = (days: number) => {
    setPage(1);
    setDaysBack(days);
  };

  const handleLogout = async () => {
    await api.logout();
    navigate("/login", { replace: true });
  };

  const showSkeleton = loading && !data && !error;
  // Only render the full dashboard when metrics are present.
  // If the backend returns data with metrics: null (empty project / no issues
  // in range), we show an empty state instead of crashing KpiGrid.
  const showContent = !!data && !!data.metrics;
  const showNoData = !!data && !data.metrics;

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
        projects={data?.projects ?? []}
        projectKey={projectKey}
        setProjectKey={handleSetProjectKey}
        daysBack={daysBack}
        setDaysBack={handleSetDaysBack}
        onLogout={handleLogout}
      />


      <main className="main-content dashboard-main">
        <header className="dashboard-header fade-in-up">
          <div className="dashboard-header-text">
            <p className="eyebrow">Operations overview</p>
            <h1 className="dashboard-title">
              Project <span>Intelligence</span>
            </h1>
            <p className="dashboard-subtitle">
              Live metrics, flow health, and issue detail from Jira.
            </p>
          </div>
          <div className="header-actions dashboard-header-actions">
            <button
              type="button"
              className={`btn btn-primary ${isRefreshing ? "btn-pulse" : ""}`}
              onClick={refresh}
              disabled={loading}
            >
              {isRefreshing ? "Refreshing…" : "Refresh"}
            </button>

            <button type="button" className="btn btn-secondary" onClick={() => navigate("/ai")}>
              AI Analysis
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate("/admin")}>
              Admin
            </button>
          </div>
        </header>

        {isRefreshing && (
          <div className="dashboard-refresh-bar" aria-hidden />
        )}

        {error && <div className="error-box fade-in-up">Error: {error}</div>}

        {showSkeleton && <DashboardSkeleton />}

        {showNoData && !loading && (
          <div className="empty-state fade-in-up">
            <h2>No Data Available</h2>
            <p>
              No issues found for <strong>{data!.project_key}</strong> in the
              last {data!.days_back} days. Try a wider time range or switch to
              another project.
            </p>
          </div>
        )}

        {showContent && (
          <div className="dashboard-body stagger-children">
            <div className="fade-in-up">
              <HealthBanner
                health={data.project_health}
                projectKey={data.project_key}
                daysBack={data.days_back}
                total={data.total_issues}
              />
            </div>

            <div className="fade-in-up">
              <KpiGrid metrics={data.metrics} />
            </div>

            <section className="dashboard-section fade-in-up">
              <h2 className="sr-only">Charts</h2>
              <Suspense fallback={<LazyChartsFallback />}>
                <Charts
                  issues={data.issues_table}
                  dailyUpdateActivity={data.daily_update_activity}
                  teamActivityHeatmap={data.team_activity_heatmap}
                />
              </Suspense>
            </section>

            <section className="dashboard-section fade-in-up">
              <h2 className="section-heading">Export</h2>
              <Suspense
                fallback={
                  <div className="dash-sk-actions">
                    {[0, 1, 2, 3].map((i) => (
                      <span key={i} className="dash-sk-btn dash-skeleton-shimmer" />
                    ))}
                  </div>
                }
              >
                <ExportButtons projectKey={data.project_key} daysBack={data.days_back} />
              </Suspense>
            </section>

            <section className="dashboard-section fade-in-up">
              <h2 className="section-heading">Issues</h2>
              <Suspense fallback={<LazyTableFallback />}>
                <IssueTable issues={data.issues_table} />
              </Suspense>
            </section>

            <div className="fade-in-up">
              <PaginationControls
                page={data.page}
                pageSize={data.page_size}
                total={data.total_issues}
                onPageChange={setPage}
              />
            </div>
          </div>
        )}

        {!loading && !data && !error && (
          <div className="empty-state fade-in-up">
            <h2>No Data Found</h2>
          </div>
        )}
      </main>
    </div>
  );
};

const App: React.FC = () => {
  //const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loadingUser, setLoadingUser] = useState<boolean>(!!getToken());

  const ws = useWebSocket("global");

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    navigate("/login", { replace: true });
  };

  useEffect(() => {
    const loadUser = async () => {
      const token = getToken();
      if (!token) {
        setUser(null);
        setLoadingUser(false);
        return;
      }

      setLoadingUser(true);
      try {
        const me = await api.getMe();
        setUser(me);
      } catch {
        clearToken();
        setUser(null);
      } finally {
        setLoadingUser(false);
      }
    };

    void loadUser();
  }, []);

  return (
    <WebSocketContext.Provider value={ws}>
      <Suspense fallback={<LoadingBlock label="Loading application..." />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <RootRedirect loading={loadingUser} user={user} />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="user:manage">
                  {user ? <AdminChoicePage user={user} onLogout={handleLogout} /> : null}
                </PermissionRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="dashboard:view">
                  <Dashboard />
                </PermissionRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/ai"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="dashboard:view">
                  <AIPage />
                </PermissionRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/jira-explorer"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="dashboard:view">
                  {user ? <JiraExplorerPage user={user} onLogout={handleLogout} /> : null}
                </PermissionRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/team-scorecard"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="dashboard:view">
                  <TeamScorecardPage />
                </PermissionRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/portfolio"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="dashboard:view">
                  <PortfolioPage />
                </PermissionRoute>
              </ProtectedRoute>
            }
          />

          <Route
            path="/manage-users"
            element={
              <ProtectedRoute>
                <PermissionRoute loading={loadingUser} user={user} permission="user:manage">
                  {user ? <ManageUsersPage user={user} onLogout={handleLogout} /> : null}
                </PermissionRoute>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Suspense>
    </WebSocketContext.Provider>
  );
};

export default App;
