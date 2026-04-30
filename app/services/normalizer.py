# services/Normalisation.py

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dateutil import parser
from pydantic import BaseModel, Field

from app.adapters.jira import jira_canonical_status

# --- Pydantic Models for Issue Normalisation ---

class IdentityModel(BaseModel):
    issue_id: Optional[str] = None
    issue_key: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None

class TemporalityModel(BaseModel):
    updated_at_utc: Optional[str] = None
    days_since_update: Optional[int] = None

class SemanticsModel(BaseModel):
    status_canonical: str

class ActorModel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

class NormalizedIssueModel(BaseModel):
    identity: IdentityModel
    temporality: TemporalityModel
    semantics: SemanticsModel
    actors: Dict[str, Optional[ActorModel]]

def _extract_user(user: Optional[Dict]) -> Optional[Dict]:
    if not user:
        return None
    return {
        "id": user.get("accountId") or user.get("name") or user.get("key"),
        "name": user.get("displayName"),
    }

def normalize_issue(raw: Dict) -> Dict:
    fields = raw.get("fields", {})

    status = fields.get("status") or {}
    status_name = status.get("name")
    jira_status_category = (status.get("statusCategory") or {}).get("name")

    canonical = jira_canonical_status(
        status_name=status_name,
        jira_status_category=jira_status_category,
    )

    updated_raw = fields.get("updated")
    updated_at_utc = None
    days_since_update = None

    if updated_raw:
        try:
            updated_dt = parser.parse(updated_raw).astimezone(timezone.utc)
            updated_at_utc = updated_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            days_since_update = (datetime.now(timezone.utc) - updated_dt).days
        except Exception:
            pass

    assignee = _extract_user(fields.get("assignee"))

    model = NormalizedIssueModel(
        identity=IdentityModel(
            issue_id=raw.get("id"),
            issue_key=raw.get("key"),
            summary=fields.get("summary"),
            description=fields.get("description"),
        ),
        temporality=TemporalityModel(
            updated_at_utc=updated_at_utc,
            days_since_update=days_since_update,
        ),
        semantics=SemanticsModel(
            status_canonical=canonical,
        ),
        actors={
            "assignee": ActorModel(**assignee) if assignee else None,
            "reporter": None
        }
    )
    # Dump to dict matching original API contract
    return model.model_dump(exclude_none=False)

# --- Pydantic Models for Project Normalisation ---

class ProjectClassification(BaseModel):
    type: Optional[str] = None
    category: Optional[Dict[str, Optional[str]]] = None

class ProjectIdentity(BaseModel):
    provider: str = "jira"
    project_id: Optional[str] = None
    project_key: Optional[str] = None
    project_name: Optional[str] = None
    self_url: Optional[str] = None

class GovernanceModel(BaseModel):
    archived: bool = False

class ProjectMetadata(BaseModel):
    avatar_urls: Optional[Dict[str, str]] = None

class ResilienceModel(BaseModel):
    missing_fields: List[str]

class NormalizedProjectModel(BaseModel):
    identity: ProjectIdentity
    classification: ProjectClassification
    governance: GovernanceModel
    metadata: ProjectMetadata
    resilience: ResilienceModel

def normalize_project(raw: Dict) -> Dict:
    category = raw.get("projectCategory") or {}

    missing = []
    if not raw.get("id"): missing.append("id")
    if not raw.get("key"): missing.append("key")
    if not raw.get("name"): missing.append("name")

    model = NormalizedProjectModel(
        identity=ProjectIdentity(
            project_id=raw.get("id"),
            project_key=raw.get("key"),
            project_name=raw.get("name"),
            self_url=raw.get("self")
        ),
        classification=ProjectClassification(
            type=raw.get("projectTypeKey"),
            category={
                "id": category.get("id"),
                "name": category.get("name"),
                "description": category.get("description"),
            } if category else None
        ),
        governance=GovernanceModel(
            archived=raw.get("archived", False)
        ),
        metadata=ProjectMetadata(
            avatar_urls=raw.get("avatarUrls")
        ),
        resilience=ResilienceModel(
            missing_fields=missing
        )
    )
    return model.model_dump(exclude_none=False)

def normalize_projects(raw_list: List[Dict]) -> List[Dict]:
    return [normalize_project(p) for p in raw_list]
