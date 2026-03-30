import os
from datetime import datetime, timedelta
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()  

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def _load_secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    raise RuntimeError(
        "SECRET_KEY is not set. Add it to your environment (for example .env). "
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )


SECRET_KEY = _load_secret_key()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError("Invalid or expired token") from e
