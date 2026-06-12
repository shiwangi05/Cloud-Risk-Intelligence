"""
routers/auth.py
JWT-based authentication — register, login, and get_current_user dependency.

Endpoints:
  POST /auth/register  – create a new user account
  POST /auth/token     – login and receive a JWT access token
  GET  /auth/me        – return the currently authenticated user
"""

from datetime import timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Crypto config ──────────────────────────────────────────────────────────────
# sha256_crypt is built into passlib — no external bcrypt version conflicts
_pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# ── Internal helpers ───────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _create_access_token(data: dict) -> str:
    from datetime import datetime, timezone
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def _get_user(db: Session, username: str) -> models.User | None:
    return db.query(models.User).filter(models.User.username == username).first()


# ── Shared dependency — use this in any protected route ───────────────────────

def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """FastAPI dependency: decode the JWT and return the active user."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_error
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_error

    user = _get_user(db, token_data.username)
    if user is None or not user.is_active:
        raise credentials_error
    return user


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a new user account."""
    if _get_user(db, user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already taken.",
        )
    db_user = models.User(
        username=user_in.username,
        hashed_password=_hash_password(user_in.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/token", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login and receive a JWT bearer token.
    Uses standard OAuth2 form fields: username + password.
    """
    user = _get_user(db, form_data.username)
    if not user or not _verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")

    token = _create_access_token({"sub": user.username})
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user
