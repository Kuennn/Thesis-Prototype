# routers/auth.py
# Teacher authentication — login, JWT token, password management
#
# Default credentials (change after first login):
#   username: admin
#   password: examcheck2024
#
# To change password: POST /api/auth/change-password

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database.database import get_db
from datetime import datetime, timedelta, timezone
import os

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# ─── Config ───────────────────────────────────────────────────────────────────

SECRET_KEY      = os.getenv("SECRET_KEY", "examcheck-ai-secret-key-change-in-production")
ALGORITHM       = "HS256"
TOKEN_EXPIRE_H  = 24  # hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ─── In-memory teacher store (simple, no DB table needed) ────────────────────
# For a real deployment this would be a DB table.
# For thesis purposes, single teacher account stored in memory.

_TEACHER = {
    "username": os.getenv("TEACHER_USERNAME", "admin"),
    "password": os.getenv("TEACHER_PASSWORD", "examcheck2024"),
    "name":     os.getenv("TEACHER_NAME",     "Teacher"),
}


# ─── Schemas ──────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type:   str
    teacher_name: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password:     str


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def create_token(data: dict) -> str:
    try:
        from jose import jwt
    except ImportError:
        # Fallback: simple base64 token if jose not installed
        import base64, json
        payload = {**data, "exp": (datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_H)).isoformat()}
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()

    payload = {
        **data,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_H),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        from jose import jwt, JWTError
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        pass

    # Fallback base64
    try:
        import base64, json
        payload = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        exp = datetime.fromisoformat(payload.get("exp", ""))
        if datetime.now(timezone.utc) > exp:
            return None
        return payload
    except Exception:
        return None


def get_current_teacher(token: str = Depends(oauth2_scheme)):
    payload = verify_token(token)
    if not payload or payload.get("sub") != _TEACHER["username"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token, summary="Teacher login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates the teacher with username + password.
    Returns a JWT token valid for 24 hours.
    """
    if (form.username != _TEACHER["username"] or
        form.password != _TEACHER["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_token({"sub": _TEACHER["username"]})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "teacher_name": _TEACHER["name"],
    }


@router.get("/me", summary="Get current teacher info")
def get_me(current: dict = Depends(get_current_teacher)):
    return {
        "username":     _TEACHER["username"],
        "name":         _TEACHER["name"],
        "token_valid":  True,
    }


@router.post("/change-password", summary="Change teacher password")
def change_password(
    payload: ChangePasswordIn,
    current: dict = Depends(get_current_teacher),
):
    if payload.current_password != _TEACHER["password"]:
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
    _TEACHER["password"] = payload.new_password
    return {"message": "Password changed successfully."}


@router.post("/logout", summary="Logout (client-side token deletion)")
def logout():
    # JWT is stateless — actual logout is done client-side by deleting the token.
    return {"message": "Logged out successfully."}
