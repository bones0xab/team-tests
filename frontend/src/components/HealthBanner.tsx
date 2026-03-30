import React from "react";

interface Props {
  health: string;
  projectKey: string;
  daysBack: number;
  total: number;
}



const HealthBanner: React.FC<Props> = ({ health, projectKey, daysBack, total }) => (
  <div className={`health-banner ${health.replace(' ', '-')} fade-in`}>
    <div className="health-dot" />
    <div>
      <div className="health-label">Project Health Status</div>
      <div className="health-status">{health}</div>
    </div>
    <div className="health-meta">
      {projectKey} &nbsp;·&nbsp; Last {daysBack} days &nbsp;·&nbsp; {total} issues
    </div>
  </div>
);

export default React.memo(HealthBanner);
