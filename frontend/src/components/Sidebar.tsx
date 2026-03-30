import React, { useState, useEffect } from "react";

interface Project {
  identity: {
    project_key: string;
    project_name: string;
  };
}

interface SidebarProps {
  open: boolean;
  projects: Project[];
  projectKey: string | null;
  setProjectKey: (v: string) => void;
  daysBack: number;
  setDaysBack: (v: number) => void;
  onLogout: () => void | Promise<void>;
}

const DAY_OPTIONS = [
  { label: "Last 7 days", value: 7 },
  { label: "Last 30 days", value: 30 },
  { label: "Last 90 days", value: 90 },
];

const Sidebar: React.FC<SidebarProps> = ({
  open,
  projects,
  projectKey,
  setProjectKey,
  daysBack,
  setDaysBack,
  onLogout,
}) => {
  const now = new Date();
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    return (localStorage.getItem("theme") as "light" | "dark") || "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === "dark" ? "light" : "dark");

  return (
    <aside className={`sidebar${open ? " open" : ""}`}>
      <div className="sidebar-logo">
        <img src="/logo.webp" alt="NTT DATA" className="sidebar-logo-img" fetchPriority="high" />
        <button
          onClick={toggleTheme}
          className="theme-toggle"
          type="button"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>

      <div className="sidebar-section">
        <h3>Navigation</h3>
        <div className="sidebar-nav">
          <button
            className={`btn btn-sidebar ${window.location.pathname === "/portfolio" ? "active" : ""}`}
            onClick={() => window.location.href = "/portfolio"}
            type="button"
          >
            Portfolio
          </button>
          <button
            className={`btn btn-sidebar ${window.location.pathname === "/dashboard" ? "active" : ""}`}
            onClick={() => window.location.href = "/dashboard"}
            type="button"
          >
            Project Dashboard
          </button>
          <button
            className={`btn btn-sidebar ${window.location.pathname === "/team-scorecard" ? "active" : ""}`}
            onClick={() => window.location.href = "/team-scorecard"}
            type="button"
          >
            Team Scorecard
          </button>
        </div>
        <hr />
      </div>

      <div className="sidebar-section">
        <h3>Project</h3>
        <div className="sidebar-field">
          <label>Project</label>
          <select value={projectKey ?? ""} onChange={(e) => setProjectKey(e.target.value)}>
            {projects.map((project) => (
              <option key={project.identity.project_key} value={project.identity.project_key}>
                {project.identity.project_name} ({project.identity.project_key})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="sidebar-section">
        <h3>Time Range</h3>
        <div className="sidebar-field">
          <label>Analysis Period</label>
          <select value={daysBack} onChange={(e) => setDaysBack(Number(e.target.value))}>
            {DAY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>


      <div className="sidebar-section">
        <h3>Session</h3>
        <div className="sidebar-actions">
          <button className="btn btn-danger sidebar-logout-btn" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>

      <div className="sidebar-meta">
        Version 2.0
        <br />
        LangChain - Ollama - FastAPI - React
        <br />
        {now.toISOString().slice(0, 16).replace("T", " ")}
      </div>
    </aside>
  );
};

export default React.memo(Sidebar);