# routers/api_key.py
from fastapi import Header, HTTPException, status
import os

def get_api_key(api_key: str = Header(..., alias="api-key")):
    env_keys = os.getenv("API_KEYS", "")
    allowed = [k.strip() for k in env_keys.split(",") if k.strip()]
    if api_key not in allowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return api_key
