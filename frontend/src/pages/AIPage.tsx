import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useWebSocketContext } from "../hooks/useWebSocket";
import "./AIPage.css";

type AIResponse = {
  project_health: "HEALTHY" | "WARNING" | "AT RISK" | "UNKNOWN" | string;
  risks: string[];
  actions: string[];
};

const AIPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [projects, setProjects] = useState<{ key: string; name: string }[]>([]);
  const [projectKey, setProjectKey] = useState("");
  const [data, setData] = useState<AIResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Listen for real-time AI_UPDATE messages from the WebSocket
  const { lastMessage } = useWebSocketContext();

  useEffect(() => {
    if (lastMessage?.type === "AI_UPDATE" && lastMessage.data) {
      setData(lastMessage.data as AIResponse);
      setLoading(false);
    }
  }, [lastMessage]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoadingProjects(true);
        const list = await api.getAIProjects();
        if (cancelled) return;
        setProjects(list);
        if (list.length > 0) {
          setProjectKey(list[0].key);
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load projects.");
        }
      } finally {
        if (!cancelled) setLoadingProjects(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const fetchAIInsights = async () => {
    if (loading || !projectKey) return;

    setLoading(true);
    setError(null);
    setData(null);

    try {
      // The HTTP request triggers the Groq call which will broadcast via WS.
      // We also accept the HTTP response as a fallback.
      const res = await api.getAIInsights(projectKey);
      setData(res);
    } catch {
      setError("Failed to generate AI insights. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const health = data?.project_health ?? "UNKNOWN";

  return (
    <div
      className="fade-in"
      style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 1rem" }}
    >
      <div className="page-header">
        <div className="header-top">
          <div>
            <div className="header-eyebrow">AI SYSTEM</div>
            <div className="header-title">
              Project <span>Intelligence</span>
            </div>
            <div className="header-sub">
              Automated risk detection and strategic recommendations
            </div>
          </div>

          <div className="header-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/dashboard")}
            >
              ← Dashboard
            </button>
            <select
              className="input"
              aria-label="Select Project"
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              disabled={loading || loadingProjects}
              style={{ marginRight: "0.5rem" }}
            >
              {loadingProjects ? (
                <option>Loading projects...</option>
              ) : (
                projects.map((project) => (
                  <option key={project.key} value={project.key}>
                    {project.name} ({project.key})
                  </option>
                ))
              )}
            </select>
            <button
              className="btn btn-primary"
              onClick={fetchAIInsights}
              disabled={loading || loadingProjects || !projectKey}
            >
              {loading ? "Analyzing..." : "Generate AI Analysis"}
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          Generating AI insights via WebSocket stream...
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {!loading && !data && !error && (
        <div className="empty-state">
          <h2>No AI Analysis Yet</h2>
          <p>
            Select a project and click <strong>Generate AI Analysis</strong> to
            evaluate the latest health, risks, and recommended actions.
          </p>
        </div>
      )}

      {data && (
        <>
          <div className={`health-banner ${health.replace(' ', '-')}`}>
            <div className="health-dot" />
            <div>
              <div className="health-label">Project Health</div>
              <div className="health-status">{health}</div>
            </div>
            <div className="health-meta">AI Generated Insight</div>
          </div>

          <div className="ai-grid">
            <div className="ai-card">
              <div className="ai-card-title">Identified Risks</div>
              {(data.risks ?? []).length === 0 ? (
                <div className="ai-item">No significant risks detected.</div>
              ) : (
                data.risks.map((risk, index) => (
                  <div key={index} className="ai-item risk">
                    {risk}
                  </div>
                ))
              )}
            </div>

            <div className="ai-card">
              <div className="ai-card-title">Recommended Actions</div>
              {(data.actions ?? []).length === 0 ? (
                <div className="ai-item">No actions recommended at this time.</div>
              ) : (
                data.actions.map((action, index) => (
                  <div key={index} className="ai-item action">
                    {action}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default AIPage;