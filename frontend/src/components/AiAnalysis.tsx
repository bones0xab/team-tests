import React from "react";
import type { Rules } from "../api/client";

interface Props {
  rules: Rules;
}

const AiAnalysis: React.FC<Props> = ({ rules }) => {
  const risks = rules.risks ?? [];
  const actions = rules.actions ?? [];

  if (risks.length === 0 && actions.length === 0) {
    return (
      <div className="ai-card fade-in">
        <div className="ai-card-title">AI Analysis</div>
        <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
          No risks or actions identified for this project.
        </p>
      </div>
    );
  }

  return (
    <div className="ai-grid fade-in">
      {risks.length > 0 && (
        <div className="ai-card">
          <div className="ai-card-title">
            <span>⚠</span> Identified Risks
          </div>
          {risks.map((r, i) => (
            <div key={i} className="ai-item risk">{r}</div>
          ))}
        </div>
      )}
      {actions.length > 0 && (
        <div className="ai-card">
          <div className="ai-card-title">
            <span>→</span> Recommended Actions
          </div>
          {actions.map((a, i) => (
            <div key={i} className="ai-item action">{a}</div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AiAnalysis;
