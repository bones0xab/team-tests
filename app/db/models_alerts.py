# app/db/models_alerts.py

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id:              Mapped[int]            = mapped_column(primary_key=True, index=True)
    project_key:     Mapped[str]            = mapped_column(String(50), index=True, nullable=False)
    severity:        Mapped[str]            = mapped_column(String(20), nullable=False)
    status:          Mapped[str]            = mapped_column(String(20), nullable=False)
    summary:         Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    description:     Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    jira_ticket:     Mapped[Optional[str]]  = mapped_column(String(50), nullable=True)
    acknowledged:    Mapped[bool]           = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at:     Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fired_at:        Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow)
    teams_notified:  Mapped[bool]           = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "project_key":      self.project_key,
            "severity":         self.severity,
            "status":           self.status,
            "summary":          self.summary,
            "description":      self.description,
            "jira_ticket":      self.jira_ticket,
            "acknowledged":     self.acknowledged,
            "acknowledged_by":  self.acknowledged_by,
            "acknowledged_at":  str(self.acknowledged_at) if self.acknowledged_at else None,
            "resolved_at":      str(self.resolved_at) if self.resolved_at else None,
            "fired_at":         str(self.fired_at),
            "teams_notified":   self.teams_notified,
        }
        
class ProjectHealthState(Base):
    """Tracks the last known health state of each project — used to detect changes."""
    __tablename__ = "project_health_state"

    id:           Mapped[int]           = mapped_column(primary_key=True, index=True)
    project_key:  Mapped[str]           = mapped_column(String(50), unique=True, index=True, nullable=False)
    health:       Mapped[str]           = mapped_column(String(20), nullable=False)  # HEALTHY / WARNING / AT RISK
    updated_at:   Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    alerted_at:   Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)