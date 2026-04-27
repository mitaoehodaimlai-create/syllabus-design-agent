"""
STEP 4 — Authentication Routes
---------------------------------
POST /auth/register  →  create account (anyone can register as 'user')
POST /auth/login     →  returns JWT token
GET  /auth/me        →  returns your own profile (any authenticated user)

STEP-BY-STEP REGISTER FLOW:
  1. Client sends { username, email, password, role }
  2. Pydantic validates the request body (Step 3)
  3. Check duplicate username/email → 409 Conflict
  4. Hash the password with bcrypt (Step 2A)
  5. INSERT into users table (Step 1)
  6. Return 201 Created

STEP-BY-STEP LOGIN FLOW:
  1. Client sends form data: username + password
     (OAuth2PasswordRequestForm is the FastAPI standard for /token endpoints)
  2. Load user by username from DB
  3. verify_password(plaintext, stored_hash) — if False → 401
  4. Check is_active — if False → 400
  5. Build JWT payload { sub: user_id, role: role }
  6. Sign and return JWT
"""

from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from api.database import create_user, get_user_by_username
from api.schemas import LoginResponse, RegisterRequest, RegisterResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── REGISTER ─────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(body: RegisterRequest):
    """
    STEP 4A: Registration endpoint.
    Anyone can create a 'user' account.
    Only a super-admin (manual DB insert) should create 'admin' accounts
    — or you can restrict role='admin' here if needed.
    """
    # 1. Hash before touching the DB
    hashed = hash_password(body.password)

    # 2. Insert — IntegrityError fires if username/email already exists
    try:
        user = create_user(
            username=body.username,
            email=body.email,
            hashed_password=hashed,
            role=body.role,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    return RegisterResponse(
        **user,
        message=f"Account created. Role: {user['role']}",
    )


# ── LOGIN ─────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login and receive a JWT access token",
)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    STEP 4B: Login endpoint.
    FastAPI's OAuth2PasswordRequestForm automatically reads
    Content-Type: application/x-www-form-urlencoded with fields:
      username=...&password=...

    Returns a Bearer JWT that the client must include in every
    subsequent request header:
      Authorization: Bearer <token>
    """
    # 1. Look up user
    user = get_user_by_username(form.username)

    # 2. Wrong username OR wrong password → same vague error
    #    (don't reveal which one failed — prevents user enumeration)
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Disabled account
    if not user["is_active"]:
        raise HTTPException(status_code=400, detail="Account is disabled")

    # 4. Build JWT payload and sign
    token = create_access_token({"sub": user["id"], "role": user["role"]})

    return LoginResponse(
        access_token=token,
        role=user["role"],
        username=user["username"],
    )


# ── PROFILE ───────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get your own profile (requires login)",
)
def me(current_user=Depends(get_current_user)):
    """
    STEP 4C: Any authenticated user can view their own profile.
    `get_current_user` dependency (Step 2E) handles token validation.
    """
    return UserProfile(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        role=current_user["role"],
        is_active=bool(current_user["is_active"]),
    )
