"""
FaultLens API Router - Authentication & User Profile
Provides secure login, RBAC token issuance, and current session validation.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from backend.models import UserLoginModel, TokenResponseModel
from security.rbac import USERS_DB, hash_password, create_access_token, get_current_user, Role

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponseModel)
async def login(credentials: UserLoginModel):
    user = USERS_DB.get(credentials.username.strip().lower())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    hashed_input = hash_password(credentials.password)
    if user["password_hash"] != hashed_input:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    access_token = create_access_token(username=user["username"], role=user["role"])
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "name": user["name"],
            "role": user["role"].value
        }
    }


@router.get("/me")
async def get_current_user_profile(current_user=Depends(get_current_user)):
    return {
        "username": current_user.get("username"),
        "name": current_user.get("name"),
        "role": current_user.get("role")
    }
