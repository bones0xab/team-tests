import React, { useState } from "react";

interface Props {
  health: string;
  risks: string[];
  threshold: string;
}

const LEVEL: Record<string, number> = { HEALTHY: 0, WARNING: 1, "AT RISK": 2 };

const AlertsBox: React.FC<Props> = ({ health, risks, threshold }) => {
  const [expanded, setExpanded] = useState(true);

  const shouldShow = (LEVEL[health] ?? 0) >= (LEVEL[threshold] ?? 1);
  if (!shouldShow || risks.length === 0) return null;

  return (
    <div className="alerts-box fade-in">
      <div className="alerts-header" onClick={() => setExpanded(!expanded)}>
        <span>⚠</span>
        <span>Active Alerts — {health.replace("_", " ")}</span>
        <span style={{ marginLeft: "auto" }}>{expanded ? "▲" : "▼"}</span>
      </div>
      {expanded && (
        <div className="alerts-body">
          {risks.map((r, i) => (
            <div key={i} className="risk-item">{r}</div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AlertsBox;
