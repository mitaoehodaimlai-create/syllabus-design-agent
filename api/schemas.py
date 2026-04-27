"""
STEP 3 — Request & Response Schemas
-------------------------------------
Pydantic validates every incoming request body automatically.
FastAPI returns 422 Unprocessable Entity if validation fails —
before your code even runs.
"""

from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator


# ── Registration ─────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    """
    STEP 3A: What the client sends to POST /auth/register
    role is restricted to 'admin' or 'user' via Literal type.
    """
    username: str
    email: EmailStr            # Pydantic validates email format
    password: str
    role: Literal["admin", "user"] = "user"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Reject weak passwords before they reach the DB."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("username")
    @classmethod
    def username_clean(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, digits, - and _")
        return v


class RegisterResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    message: str


# ── Login ─────────────────────────────────────────────────────────
class LoginResponse(BaseModel):
    """
    STEP 3B: What /auth/login returns.
    access_token is the signed JWT string.
    token_type is always "bearer" (OAuth2 standard).
    """
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ── Current user profile ──────────────────────────────────────────
class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool


# ── Upload ────────────────────────────────────────────────────────
class UploadResponse(BaseModel):
    """
    STEP 3C: Returned after a successful admin upload.
    job_id can be polled to check generation status.
    """
    job_id: str
    filename: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str                 # pending | processing | complete | failed
    output_md: Optional[str]
    output_pdf: Optional[str]
    error_message: Optional[str]


class UploadListItem(BaseModel):
    id: str
    filename: str
    username: str
    status: str
    created_at: str
