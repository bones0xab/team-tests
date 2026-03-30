import os


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # No embedded production credentials; local dev fallback only.
    return "sqlite:///./app.sqlite3"


DATABASE_URL = _database_url()
