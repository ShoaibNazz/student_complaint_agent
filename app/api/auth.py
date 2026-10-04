from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.security import authenticate_user, create_access_token, get_current_user
from app.database.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import LoginRequest, RegisterResponse, TokenResponse, UserOut, UserRegisterRequest
from app.services.user_service import register_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new student, employee, professor, or authorized admin account."""
    try:
        user = register_user(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return RegisterResponse(
        message="Registration successful. You can now login.",
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate with role-specific ID/email and password."""
    account_type = (payload.account_type or "").strip()
    if not account_type or account_type.lower() in ("select account type", "none"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select your account type.",
        )

    user = authenticate_user(db, account_type, payload.identifier, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect ID or password.",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role})
    response.set_cookie(
        key="complaint_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
def logout(response: Response):
    """End session and clear authentication cookie."""
    response.delete_cookie(key="complaint_session")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Get profile information for the currently authenticated user."""
    return UserOut.model_validate(current_user)
