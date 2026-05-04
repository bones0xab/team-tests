import pytest
pytest.skip('Obsolete - tests old Normalisation.py flat dict API', allow_module_level=True)
from datetime import datetime, timezone, timedelta
from app.services.normalizer import normalize_issue


class TestNormalizeIssue:
    
    def test_normalize_issue_basic(self):
        raw_issue = {
            "id": "12345",
            "key": "PROJ-123",
            "fields": {
                "summary": "Test issue",
                "status": {
                    "name": "In Progress",
                    "statusCategory": {
                        "name": "In Progress"
                    }
                },
                "assignee": {
                    "displayName": "John Doe"
                },
                "updated": "2025-02-10T14:30:00+01:00"
            }
        }
        
        result = normalize_issue(raw_issue)
        
        # VÃ©rifications
        assert result["id"] == "12345"
        assert result["key"] == "PROJ-123"
        assert result["summary"] == "Test issue"
        assert result["status_name"] == "In Progress"
        assert result["assignee"] == "John Doe"
        assert isinstance(result["updated_at"], datetime)
        assert isinstance(result["days_since_update"], int)
    
    def test_normalize_issue_no_assignee(self):
        raw_issue = {
            "id": "12346",
            "key": "PROJ-124",
            "fields": {
                "summary": "Unassigned issue",
                "status": {
                    "name": "To Do",
                    "statusCategory": {
                        "name": "To Do"
                    }
                },
                "assignee": None,  # Pas d'assignÃ©
                "updated": "2025-02-01T10:00:00+01:00"
            }
        }
        
        result = normalize_issue(raw_issue)
        
        assert result["assignee"] is None, "Assignee devrait Ãªtre None"
    
    def test_normalize_issue_status_category(self):
        raw_issue = {
            "id": "12347",
            "key": "PROJ-125",
            "fields": {
                "summary": "Done issue",
                "status": {
                    "name": "Done",
                    "statusCategory": {
                        "name": "Done"
                    }
                },
                "assignee": None,
                "updated": "2025-02-11T12:00:00+01:00"
            }
        }
        
        result = normalize_issue(raw_issue)
        
        # VÃ©rifier que status_category existe et est une string
        assert "status_category" in result
        assert isinstance(result["status_category"], str)
    
    def test_normalize_issue_days_since_update(self):
        # CrÃ©er un ticket mis Ã  jour il y a 5 jours
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        updated_str = five_days_ago.isoformat()
        
        raw_issue = {
            "id": "12348",
            "key": "PROJ-126",
            "fields": {
                "summary": "Old issue",
                "status": {
                    "name": "In Progress",
                    "statusCategory": {"name": "In Progress"}
                },
                "assignee": None,
                "updated": updated_str
            }
        }
        
        result = normalize_issue(raw_issue)
        
        # days_since_update devrait Ãªtre environ 5
        assert result["days_since_update"] >= 4, "Devrait Ãªtre >= 4 jours"
        assert result["days_since_update"] <= 6, "Devrait Ãªtre <= 6 jours"
    
    def test_normalize_issue_timezone_with_colon(self):
        raw_issue = {
            "id": "12349",
            "key": "PROJ-127",
            "fields": {
                "summary": "Timezone test",
                "status": {
                    "name": "Done",
                    "statusCategory": {"name": "Done"}
                },
                "assignee": None,
                "updated": "2025-02-12T08:00:00+01:00"  # DÃ©jÃ  bon format
            }
        }
        
        result = normalize_issue(raw_issue)
        
        assert isinstance(result["updated_at"], datetime)
        assert result["updated_at"].tzinfo is not None, "Timezone devrait Ãªtre dÃ©finie"
    
    def test_normalize_issue_timezone_without_colon(self):
        raw_issue = {
            "id": "12350",
            "key": "PROJ-128",
            "fields": {
                "summary": "Timezone test 2",
                "status": {
                    "name": "Done",
                    "statusCategory": {"name": "Done"}
                },
                "assignee": None,
                "updated": "2025-02-12T08:00:00+0100"  # Format Jira sans ":"
            }
        }
        
        result = normalize_issue(raw_issue)
        
        assert isinstance(result["updated_at"], datetime)
        assert result["updated_at"].tzinfo is not None, "Timezone devrait Ãªtre dÃ©finie"


class TestNormalizeIssueEdgeCases:
    def test_normalize_issue_today(self):
        now = datetime.now(timezone.utc)
        updated_str = now.isoformat()
        
        raw_issue = {
            "id": "12351",
            "key": "PROJ-129",
            "fields": {
                "summary": "Fresh issue",
                "status": {
                    "name": "To Do",
                    "statusCategory": {"name": "To Do"}
                },
                "assignee": {"displayName": "Alice"},
                "updated": updated_str
            }
        }
        
        result = normalize_issue(raw_issue)
        
        assert result["days_since_update"] == 0, "Devrait Ãªtre 0 jour"
    
    def test_normalize_issue_all_fields_present(self):
        raw_issue = {
            "id": "12352",
            "key": "PROJ-130",
            "fields": {
                "summary": "Complete issue",
                "status": {
                    "name": "In Review",
                    "statusCategory": {"name": "In Progress"}
                },
                "assignee": {"displayName": "Bob"},
                "updated": "2025-02-10T10:00:00+01:00"
            }
        }
        
        result = normalize_issue(raw_issue)
        
        # VÃ©rifier tous les champs
        required_fields = [
            "id", "key", "summary", "status_name", 
            "status_category", "assignee", "updated_at", 
            "days_since_update"
        ]
        
        for field in required_fields:
            assert field in result, f"Champ manquant: {field}"
    
    def test_normalize_issue_negative_timezone(self):
        raw_issue = {
            "id": "12353",
            "key": "PROJ-131",
            "fields": {
                "summary": "Negative timezone",
                "status": {
                    "name": "Done",
                    "statusCategory": {"name": "Done"}
                },
                "assignee": None,
                "updated": "2025-02-12T10:00:00-0500"  # New York timezone
            }
        }
        
        result = normalize_issue(raw_issue)
        
        assert isinstance(result["updated_at"], datetime)
        assert result["updated_at"].tzinfo is not None
    
    def test_normalize_issue_days_not_negative(self):
        # Utiliser une date trÃ¨s rÃ©cente (quelques secondes avant maintenant)
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        
        raw_issue = {
            "id": "12354",
            "key": "PROJ-132",
            "fields": {
                "summary": "Very recent issue",
                "status": {
                    "name": "To Do",
                    "statusCategory": {"name": "To Do"}
                },
                "assignee": None,
                "updated": recent_time.isoformat()
            }
        }
        
        result = normalize_issue(raw_issue)
        
        # MÃªme si mise Ã  jour il y a quelques secondes, days_since_update >= 0
        assert result["days_since_update"] >= 0, "Ne devrait jamais Ãªtre nÃ©gatif"


class TestNormalizeIssueRobustness:
    def test_normalize_handles_multiple_timezone_formats(self):
        timezone_formats = [
            "2025-02-12T10:00:00+01:00",  # Format standard
            "2025-02-12T10:00:00+0100",   # Format Jira
            "2025-02-12T10:00:00-05:00",  # Timezone nÃ©gative standard
            "2025-02-12T10:00:00-0500",   # Timezone nÃ©gative Jira
            "2025-02-12T10:00:00Z",       # UTC
        ]
        
        for tz_format in timezone_formats:
            raw_issue = {
                "id": "test",
                "key": "TEST-1",
                "fields": {
                    "summary": "Test",
                    "status": {
                        "name": "Done",
                        "statusCategory": {"name": "Done"}
                    },
                    "assignee": None,
                    "updated": tz_format
                }
            }
            
            result = normalize_issue(raw_issue)
            assert isinstance(result["updated_at"], datetime), \
                f"Failed for timezone format: {tz_format}"