"""
STEP 2 — Authentication Core
------------------------------
Two responsibilities:
  A) Password hashing   — bcrypt (used directly, avoids passlib/Python-3.13 bug)
  B) JWT tokens         — signed with HS256 via python-jose

Flow:
  Register  → hash plaintext password → store hash (NEVER store plaintext)
  Login     → re-hash input → compare → issue JWT
  Request   → decode JWT → load user → check role
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from api.database import get_user_by_id, get_user_by_username

# ── secrets (load from env in production) ────────────────────────
SECRET_KEY  = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-32-char-random")
ALGORITHM   = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 8   # 8 hours

# ── OAuth2 scheme: FastAPI reads Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────────────────────────
# A) PASSWORD HELPERS  (bcrypt used directly — no passlib wrapper)
# ─────────────────────────────────────────────────────────────────

def hash_password(plaintext: str) -> str:
    """
    STEP 2A: bcrypt hash.
    bcrypt automatically:
      - generates a unique salt per call
      - embeds the salt in the output string
      - does N rounds of work (rounds=12) to slow brute-force
    Output looks like: $2b$12$<22-char-salt><31-char-hash>
    """
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """
    STEP 2B: constant-time comparison prevents timing attacks.
    bcrypt.checkpw extracts the salt from `hashed` automatically.
    """
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())


# ─────────────────────────────────────────────────────────────────
# B) JWT HELPERS
# ─────────────────────────────────────────────────────────────────

def create_access_token(payload: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    STEP 2C: Build and sign a JWT.
    The payload (claims) contains:
      sub  — subject = user ID
      role — the user's role (admin | user)
      exp  — expiry timestamp (auto-checked on decode)
    """
    data = payload.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    )
    data["exp"] = expire
    # jwt.encode signs data with SECRET_KEY using ALGORITHM
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    STEP 2D: Decode and verify the JWT signature.
    Raises JWTError if:
      - signature is invalid (tampered)
      - token is expired
      - algorithm doesn't match
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ─────────────────────────────────────────────────────────────────
# C) FASTAPI DEPENDENCY: get the current authenticated user
# ─────────────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    STEP 2E: FastAPI dependency injected into any protected route.

    Execution order:
      1. FastAPI extracts Bearer token from Authorization header
      2. Decode + verify JWT signature
      3. Pull user ID from 'sub' claim
      4. Load user from database
      5. Confirm user is still active
      6. Return user row → available in route handler
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return user


# ─────────────────────────────────────────────────────────────────
# D) ROLE GUARD: admin-only dependency
# ─────────────────────────────────────────────────────────────────

def require_admin(current_user=Depends(get_current_user)):
    """
    STEP 2F: Layer on top of get_current_user.
    If role != 'admin' → 403 Forbidden (user IS authenticated but NOT authorized).

    Usage in a route:
        @router.post("/upload")
        def upload(user = Depends(require_admin)):
            ...
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this action",
        )
    return current_user
