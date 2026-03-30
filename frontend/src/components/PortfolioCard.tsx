import React from "react";
import { useNavigate } from "react-router-dom";

interface PortfolioItem {
  project_key: string;
  project_name: string;
  health: "HEALTHY" | "WARNING" | "AT RISK" | "UNKNOWN";
  total_issues: number;
  wip_count: number;
  stale_count: number;
}

interface Props {
  item: PortfolioItem;
}

const PortfolioCard: React.FC<Props> = ({ item }) => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/dashboard?project_key=${item.project_key}`);
  };

  return (
    <div className={`portfolio-card ${item.health.replace(" ", "-")} fade-in`} onClick={handleClick}>
      <div className="portfolio-card-header">
        <div className="portfolio-card-title-wrap">
          <h3 className="portfolio-card-title">{item.project_name}</h3>
          <span className="portfolio-card-key">{item.project_key}</span>
        </div>
        <div className={`portfolio-health-indicator ${item.health.replace(" ", "-")}`}>
          {item.health}
        </div>
      </div>

      <div className="portfolio-card-body">
        <div className="portfolio-stat">
          <span className="portfolio-stat-label">Total</span>
          <span className="portfolio-stat-value">{item.total_issues}</span>
        </div>
        <div className="portfolio-stat">
          <span className="portfolio-stat-label">WIP</span>
          <span className="portfolio-stat-value">{item.wip_count}</span>
        </div>
        <div className="portfolio-stat">
          <span className="portfolio-stat-label">Stale</span>
          <span className={`portfolio-stat-value ${item.stale_count > 0 ? "text-orange" : ""}`}>
            {item.stale_count}
          </span>
        </div>
      </div>

      <div className="portfolio-card-footer">
        <span className="portfolio-view-details">View Details →</span>
      </div>
    </div>
  );
};

export default PortfolioCard;
