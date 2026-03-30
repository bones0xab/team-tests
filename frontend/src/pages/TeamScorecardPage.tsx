import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type TeamScorecardResponse, type TeamSprint } from "../api/client";
import { useWebSocketContext } from "../hooks/useWebSocket";
import "./TeamScorecardPage.css";

const TeamScorecardPage: React.FC = () => {
  const navigate = useNavigate();
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [projects, setProjects] = useState<{ key: string; name: string }[]>([]);
  const [projectKey, setProjectKey] = useState("");
  
  const [loadingSprints, setLoadingSprints] = useState(false);
  const [sprints, setSprints] = useState<TeamSprint[]>([]);
  const [sprintId, setSprintId] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TeamScorecardResponse | null>(null);
  const [streamingMembers, setStreamingMembers] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"score" | "name" | "overdue" | "blocked" | "completed">("score");

  // Subscribe to SCORECARD_TOKEN WebSocket messages for real-time streaming
  const { lastMessage } = useWebSocketContext();

  useEffect(() => {
    if (lastMessage?.type === "SCORECARD_TOKEN" && lastMessage.user && lastMessage.data) {
      setStreamingMembers((prev) => ({
        ...prev,
        [lastMessage.user as string]: lastMessage.data,
      }));
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
        if (!cancelled) setError("Failed to load projects.");
      } finally {
        if (!cancelled) setLoadingProjects(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!projectKey) return;
    let cancelled = false;
    (async () => {
      try {
        setLoadingSprints(true);
        setSprints([]);
        setSprintId("");
        const res = await api.getTeamSprints(projectKey);
        if (cancelled) return;
        setSprints(res.sprints);
        if (res.sprints.length > 0) {
          setSprintId(res.sprints[0].id);
        }
      } catch {
        // ignore fetch sprint errors to allow fallback or empty state
      } finally {
        if (!cancelled) setLoadingSprints(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectKey]);

  const fetchScorecard = async () => {
    if (loading || !projectKey || !sprintId) return;

    setLoading(true);
    setError(null);
    setStreamingMembers({}); // reset streaming state before a fresh fetch

    try {
      const res = await api.getTeamScorecard(projectKey, sprintId);
      setData(res);
    } catch {
      setError("Failed to fetch team scorecard. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Merge the full final HTTP response with any streaming updates received via WS
  const members = data?.members ?? [];
  const mergedMembers = members.map((m) => {
    const stream = streamingMembers[m.displayName];
    return stream ? { ...m, ai: stream } : m;
  });

  // Also show purely streaming members not yet in the final response
  const streamingOnlyNames = Object.keys(streamingMembers).filter(
    (name) => !members.some((m) => m.displayName === name)
  );

  const sortedMembers = React.useMemo(() => {
    const arr = [...mergedMembers];
    arr.sort((a, b) => {
      if (sortBy === "score") return b.ai.performance_score - a.ai.performance_score;
      if (sortBy === "name") return a.displayName.localeCompare(b.displayName);
      if (sortBy === "overdue") return b.metrics.overdue_rate - a.metrics.overdue_rate;
      if (sortBy === "blocked") return b.metrics.blocked_tasks - a.metrics.blocked_tasks;
      if (sortBy === "completed") return b.metrics.tasks_completed - a.metrics.tasks_completed;
      return 0;
    });
    return arr;
  }, [mergedMembers, sortBy]);

  const getScoreColor = (score: number) => {
    if (score >= 90) return "#00CB5D";
    if (score >= 70) return "#0072BC";
    if (score >= 50) return "#FF7A00";
    return "#E42600";
  };

  const getLabelClass = (label: string) => {
    if (label === "Excellent") return "label-excellent";
    if (label === "Good") return "label-good";
    if (label === "Needs Attention") return "label-warning";
    return "label-risk";
  };

  const hasStreamingData = streamingOnlyNames.length > 0 || Object.keys(streamingMembers).length > 0;

  return (
    <div className="fade-in" style={{ maxWidth: "1400px", margin: "0 auto", padding: "0 1rem", paddingBottom: "3rem" }}>
      <div className="page-header">
        <div className="header-top">
          <div>
            <div className="header-eyebrow">TEAM MANAGEMENT</div>
            <div className="header-title">
              Team <span>Scorecard</span>
            </div>
            <div className="header-sub">
              Individual developer metrics, AI performance scores and velocity trends per sprint.
            </div>
          </div>

          <div className="header-actions" style={{ gap: "0.5rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/dashboard")}
              style={{ marginRight: "0.5rem" }}
            >
              ← Dashboard
            </button>
            <select
              className="input"
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              disabled={loading || loadingProjects}
            >
              {loadingProjects ? (
                <option>Loading projects...</option>
              ) : (
                projects.map((p) => (
                  <option key={p.key} value={p.key}>{p.name} ({p.key})</option>
                ))
              )}
            </select>
            <select
              className="input"
              value={sprintId}
              onChange={(e) => setSprintId(e.target.value)}
              disabled={loading || loadingSprints || sprints.length === 0}
            >
              {loadingSprints ? (
                <option>Loading sprints...</option>
              ) : sprints.length === 0 ? (
                <option value="">No sprints found</option>
              ) : (
                sprints.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.id})</option>
                ))
              )}
            </select>
            {!loadingSprints && sprints.length > 0 && (
                <div style={{ fontSize: "0.75rem", fontFamily: "var(--mono)", color: "var(--turquoise)", border: "1px solid var(--border)", padding: "0.45rem 0.6rem", borderRadius: "4px", background: "rgba(0,223,237,0.05)", fontWeight: 600 }}>
                  {sprints.length} SPRINTS
                </div>
            )}
            <button
              className="btn btn-primary"
              onClick={fetchScorecard}
              disabled={loading || loadingProjects || !projectKey || !sprintId}
            >
              {loading ? "Fetching..." : "Refresh"}
            </button>
          </div>
        </div>
      </div>

      {/* Real-time streaming indicator */}
      {loading && hasStreamingData && (
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", color: "var(--turquoise)", fontSize: "0.85rem", fontWeight: 600 }}>
          <div className="spinner" style={{ width: "14px", height: "14px" }} />
          Streaming team scores via WebSocket... ({Object.keys(streamingMembers).length} received)
        </div>
      )}

      {loading && !hasStreamingData && (
        <div className="spinner-wrap">
          <div className="spinner" />
          Analyzing team performance...
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {!loading && !data && !error && Object.keys(streamingMembers).length === 0 && (
        <div className="empty-state">
          <h2>No Scorecard Generated</h2>
          <p>Select a project and sprint above, then click <strong>Refresh</strong> to view team member performance metrics.</p>
        </div>
      )}

      {data && sortedMembers.length === 0 && (
        <div className="empty-state">
          <h2>No Team Members Found</h2>
          <p>We couldn't find any team members matched to issues in this specific sprint for {projectKey}.</p>
        </div>
      )}

      {(sortedMembers.length > 0 || streamingOnlyNames.length > 0) && (
        <>
          <div className="scorecard-controls">
            <span style={{ fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600 }}>SORT BY:</span>
            <select className="input input-sm" value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
              <option value="score">AI Score (Desc)</option>
              <option value="name">Name (A-Z)</option>
              <option value="completed">Completed Tasks (Desc)</option>
              <option value="overdue">Overdue Rate (Desc)</option>
              <option value="blocked">Blocked Tasks (Desc)</option>
            </select>
          </div>
          
          <div className="scorecard-grid">
            {sortedMembers.map(member => {
              const { avatarUrl, displayName, accountId, metrics, ai } = member;
              const maxVelocity = Math.max(...metrics.velocity_trend, 1);
              return (
                <div className="scorecard-card" key={accountId}>
                  <div className="sc-header">
                    <div className="sc-user">
                      {avatarUrl ? (
                        <img src={avatarUrl} alt={displayName} className="sc-avatar" />
                      ) : (
                        <div className="sc-avatar-placeholder">{displayName.charAt(0)}</div>
                      )}
                      <div className="sc-name">{displayName}</div>
                    </div>
                    <div className="sc-score-wrapper">
                      <div className="sc-score" style={{ color: getScoreColor(ai.performance_score) }}>
                        {ai.performance_score}
                      </div>
                      <div className={`sc-badge ${getLabelClass(ai.performance_label)}`}>
                        {ai.performance_label}
                      </div>
                    </div>
                  </div>
                  
                  <div className="sc-metrics">
                    <div className="sc-metric-pill"><span role="img" aria-label="done">✅</span> {metrics.tasks_completed} done</div>
                    <div className="sc-metric-pill"><span role="img" aria-label="progress">🔄</span> {metrics.tasks_in_progress} in progress</div>
                    <div className="sc-metric-pill"><span role="img" aria-label="todo">🔲</span> {metrics.tasks_todo} todo</div>
                    <div className="sc-metric-pill" style={{ color: metrics.blocked_tasks > 0 ? "var(--orange)" : "inherit" }}>
                      <span role="img" aria-label="blocked">⚠️</span> {metrics.blocked_tasks} blocked
                    </div>
                    <div className="sc-metric-pill" style={{ color: metrics.overdue_rate > 20 ? "var(--orange)" : "inherit" }}>
                      <span role="img" aria-label="overdue">📉</span> {metrics.overdue_rate}% overdue
                    </div>
                    <div className="sc-metric-pill"><span role="img" aria-label="time">⏱</span> {metrics.avg_resolution_time ?? "-"}d avg</div>
                  </div>
                  
                  <div className="sc-velocity">
                    <div className="sc-velocity-label">Velocity Trend (Last 4 Sprints)</div>
                    <div className="sc-bars">
                      {metrics.velocity_trend.map((val, idx) => (
                        <div key={idx} className="sc-bar-container" title={`${val} completed`}>
                          <div className="sc-bar" style={{ height: `${(val / maxVelocity) * 100}%` }}></div>
                          <span className="sc-bar-val">{val}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="sc-ai-summary">
                    <p>{ai.ai_summary}</p>
                    {ai.ai_flag && (
                      <div className="sc-flag">
                        <strong>Flag:</strong> {ai.ai_flag}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Streaming-only members that arrived via WS before the HTTP response */}
            {streamingOnlyNames.map((name) => {
              const ai = streamingMembers[name];
              return (
                <div className="scorecard-card" key={`streaming-${name}`} style={{ opacity: 0.85, border: "1px solid var(--turquoise)" }}>
                  <div className="sc-header">
                    <div className="sc-user">
                      <div className="sc-avatar-placeholder">{name.charAt(0)}</div>
                      <div className="sc-name">{name} <span style={{ fontSize: "0.7rem", color: "var(--turquoise)" }}>● LIVE</span></div>
                    </div>
                    <div className="sc-score-wrapper">
                      <div className="sc-score" style={{ color: getScoreColor(ai.performance_score) }}>
                        {ai.performance_score}
                      </div>
                      <div className={`sc-badge ${getLabelClass(ai.performance_label)}`}>
                        {ai.performance_label}
                      </div>
                    </div>
                  </div>
                  <div className="sc-ai-summary">
                    <p>{ai.ai_summary}</p>
                    {ai.ai_flag && (
                      <div className="sc-flag">
                        <strong>Flag:</strong> {ai.ai_flag}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

export default TeamScorecardPage;
