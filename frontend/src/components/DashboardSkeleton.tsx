import React from "react";

const Shimmer: React.FC<{ className?: string }> = ({ className = "" }) => (
  <span className={`dash-skeleton-shimmer ${className}`.trim()} aria-hidden />
);

export const DashboardSkeleton: React.FC = () => (
  <div className="dashboard-skeleton" aria-busy aria-label="Loading dashboard">
    <div className="dash-sk-banner">
      <Shimmer className="dash-sk-dot" />
      <div className="dash-sk-banner-text">
        <Shimmer className="dash-sk-line dash-sk-line--sm" />
        <Shimmer className="dash-sk-line dash-sk-line--lg" />
      </div>
      <Shimmer className="dash-sk-line dash-sk-line--meta" />
    </div>

    <div className="dash-sk-kpis">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="dash-sk-kpi">
          <Shimmer className="dash-sk-line dash-sk-line--xs" />
          <Shimmer className="dash-sk-line dash-sk-line--xl" />
          <Shimmer className="dash-sk-line dash-sk-line--sm" />
        </div>
      ))}
    </div>

    <div className="dash-sk-charts">
      <div className="dash-sk-chart">
        <Shimmer className="dash-sk-line dash-sk-line--xs" />
        <Shimmer className="dash-sk-chart-area" />
      </div>
      <div className="dash-sk-chart">
        <Shimmer className="dash-sk-line dash-sk-line--xs" />
        <Shimmer className="dash-sk-chart-area" />
      </div>
    </div>

    <div className="dash-sk-wide">
      <Shimmer className="dash-sk-line dash-sk-line--xs" />
      <Shimmer className="dash-sk-chart-area dash-sk-chart-area--short" />
    </div>

    <div className="dash-sk-actions">
      {[0, 1, 2, 3].map((i) => (
        <Shimmer key={i} className="dash-sk-btn" />
      ))}
    </div>

    <div className="dash-sk-table">
      <div className="dash-sk-table-head">
        {[0, 1, 2, 3, 4].map((i) => (
          <Shimmer key={i} className="dash-sk-th" />
        ))}
      </div>
      {[0, 1, 2, 3, 4, 5].map((row) => (
        <div key={row} className="dash-sk-table-row">
          {[0, 1, 2, 3, 4].map((cell) => (
            <Shimmer key={cell} className="dash-sk-td" />
          ))}
        </div>
      ))}
    </div>
  </div>
);

export const LazyChartsFallback: React.FC = () => (
  <div className="dashboard-lazy-fallback fade-in-up">
    <div className="dash-sk-charts">
      <div className="dash-sk-chart">
        <Shimmer className="dash-sk-line dash-sk-line--xs" />
        <Shimmer className="dash-sk-chart-area" />
      </div>
      <div className="dash-sk-chart">
        <Shimmer className="dash-sk-line dash-sk-line--xs" />
        <Shimmer className="dash-sk-chart-area" />
      </div>
    </div>
    <div className="dash-sk-wide">
      <Shimmer className="dash-sk-line dash-sk-line--xs" />
      <Shimmer className="dash-sk-chart-area dash-sk-chart-area--short" />
    </div>
  </div>
);

export const LazyTableFallback: React.FC = () => (
  <div className="dashboard-lazy-fallback fade-in-up" aria-busy>
    <div className="dash-sk-table">
      <div className="dash-sk-table-head">
        {[0, 1, 2, 3, 4].map((i) => (
          <Shimmer key={i} className="dash-sk-th" />
        ))}
      </div>
      {[0, 1, 2, 3, 4].map((row) => (
        <div key={row} className="dash-sk-table-row">
          {[0, 1, 2, 3, 4].map((cell) => (
            <Shimmer key={cell} className="dash-sk-td" />
          ))}
        </div>
      ))}
    </div>
  </div>
);
