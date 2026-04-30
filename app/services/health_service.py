def get_project_health_status(project_key: str, days_back: int = 30):
    from app.services.dashboard_service import fetch_dashboard_data
    
    data = fetch_dashboard_data(project_key, days_back)

    if not data:
        return None

    return {
        "status": data["rules"]["project_health"],
        "metrics": data["metrics"],
        "rules": data["rules"],
        "issues": data["issues"]
    }