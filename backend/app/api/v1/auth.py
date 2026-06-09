from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.auth_service import create_user, get_user_by_email

router = APIRouter()


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await create_user(db, user_data)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens."""
    user = await get_user_by_email(db, user_data.email)

    if not user:
        raise HTTPException(
            # Use 401 with generic message to prevent user enumeration
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    from app.core.security import verify_password

    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            # Same generic message to prevent user enumeration
            detail="Invalid email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Refresh access token using refresh token."""
    payload = verify_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """Logout user."""
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return current_user
