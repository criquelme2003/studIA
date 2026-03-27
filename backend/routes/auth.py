import logging
from fastapi import APIRouter, HTTPException, Header
from database import supabase
from models import LoginRequest, LoginResponse, TokenPayload, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def get_user_id_from_token(authorization: str) -> str:
    """
    Extract and validate a Supabase JWT.
    Expects header: Authorization: Bearer <token>
    Returns user_id (UUID string) or raises 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return str(response.user.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Token validation failed")


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    """Sign in with email and password. Returns an access token."""
    try:
        response = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
        if not response or not response.user or not response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return LoginResponse(
            access_token=response.session.access_token,
            user_id=str(response.user.id),
            email=response.user.email,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Login failed for %s: %s", payload.email, exc)
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/verify", response_model=UserResponse)
async def verify_token(payload: TokenPayload):
    """Verify a Supabase access token and return the user_id."""
    try:
        response = supabase.auth.get_user(payload.access_token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = response.user
        return UserResponse(user_id=str(user.id), email=user.email)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("verify_token error: %s", exc)
        raise HTTPException(status_code=401, detail="Token validation failed")
