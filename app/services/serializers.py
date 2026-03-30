# app/services/serializers.py

def serialize_project(project):
    return {
        "id": project.id,
        "jira_id": project.jira_id,
        "jira_key": project.jira_key,
        "name": project.name,
        "project_type": project.project_type,
        "category_name": project.category_name,
        "archived": project.archived,
        "last_synced_at": project.last_synced_at.isoformat() if project.last_synced_at else None,
        "version": project.version,
    }


def project_cache_key(jira_key: str, version: int):
    return f"project:{jira_key}:v{version}"