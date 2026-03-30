import React from "react";
import type { Metrics } from "../api/client";

interface Props {
  metrics: Metrics;
}

const KpiGrid: React.FC<Props> = ({ metrics }) => {
  const completion = metrics.done_ratio * 100;
  const wipPct = metrics.wip_ratio * 100;
  const stale = metrics.stale_in_progress_count ?? 0;
  const active = metrics.total - (metrics.done ?? 0);

  return (
    <div className="kpi-grid fade-in">
      {/* Total Issues */}
      <div className="kpi-card blue">
        <div className="kpi-label">Total Issues</div>
        <div className="kpi-value">{metrics.total.toLocaleString()}</div>
        <div className="kpi-delta neutral">{active} active</div>
      </div>

      {/* Completion Rate */}
      <div className="kpi-card cyan">
        <div className="kpi-label">Completion Rate</div>
        <div className="kpi-value">
          {completion.toFixed(1)}<span>%</span>
        </div>
        <div className={`kpi-delta ${completion >= 50 ? "positive" : "negative"}`}>
          {completion >= 50 ? "▲" : "▼"} {Math.abs(completion - 50).toFixed(1)}% vs 50% target
        </div>
      </div>

      {/* WIP */}
      <div className="kpi-card green">
        <div className="kpi-label">Work In Progress</div>
        <div className="kpi-value">
          {wipPct.toFixed(1)}<span>%</span>
        </div>
        <div className="kpi-delta neutral">{metrics.wip} issues active</div>
      </div>

      {/* Stale */}
      <div className="kpi-card yellow">
        <div className="kpi-label">Stale Issues</div>
        <div className="kpi-value">{stale}</div>
        <div className={`kpi-delta ${stale > 0 ? "negative" : "positive"}`}>
          {stale > 0 ? "Needs attention" : "All up to date"}
        </div>
      </div>
    </div>
  );
};

export default React.memo(KpiGrid);
