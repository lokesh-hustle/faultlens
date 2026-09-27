"""
FaultLens Security - Role-Based Access Control (RBAC) & Authentication
Manages User Roles (ADMIN, ENGINEER, VIEWER) and JWT Tokens.
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import jwt
import hashlib
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = "faultlens-super-secret-production-hardened-key-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours


class Role(str, Enum):
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"
    VIEWER = "VIEWER"


# Pre-configured demo users (hashed passwords)
def hash_password(password: str) -> str:
    return hashlib.sha256(f"{password}-faultlens-salt-2026".encode("utf-8")).hexdigest()


USERS_DB = {
    "admin@faultlens.io": {
        "username": "admin@faultlens.io",
        "name": "Alex Vance (Lead SRE)",
        "password_hash": hash_password("admin123!"),
        "role": Role.ADMIN
    },
    "engineer@faultlens.io": {
        "username": "engineer@faultlens.io",
        "name": "Devon Miller (Reliability Engineer)",
        "password_hash": hash_password("engineer123!"),
        "role": Role.ENGINEER
    },
    "viewer@faultlens.io": {
        "username": "viewer@faultlens.io",
        "name": "Sam Taylor (Product Operations)",
        "password_hash": hash_password("viewer123!"),
        "role": Role.VIEWER
    }
}


def create_access_token(username: str, role: Role, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": username,
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security Token Has Expired. Please Re-authenticate."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization Token Signature."
        )


security_bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)) -> Dict[str, Any]:
    if not credentials:
        # Default fallback to Admin for seamless demo experience when unauthenticated
        return {"username": "admin@faultlens.io", "name": "Alex Vance (Lead SRE)", "role": Role.ADMIN}

    payload = verify_token(credentials.credentials)
    username = payload.get("sub")
    user = USERS_DB.get(username)
    if not user:
        return {"username": username, "name": username, "role": Role(payload.get("role", Role.VIEWER))}
    return user


def require_role(min_role: Role):
    role_hierarchy = {Role.VIEWER: 1, Role.ENGINEER: 2, Role.ADMIN: 3}

    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = Role(current_user.get("role", Role.VIEWER))
        if role_hierarchy[user_role] < role_hierarchy[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Action requires [{min_role.value}] privileges. Your role: [{user_role.value}]."
            )
        return current_user

    return role_checker
