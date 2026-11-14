from collections.abc import Generator
from typing import Annotated
import uuid
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token, hash_password
from app.db.models.user import User
from app.db.session import get_db

DEMO_USER_EMAIL = "demo@example.com"

def get_demo_user(db: Session) -> User:
    """Ensure a default demo user exists for local dev and testing."""
    user = db.scalar(select(User).where(User.email == DEMO_USER_EMAIL))
    if not user:
        user = User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            email=DEMO_USER_EMAIL,
            password_hash=hash_password("demopassword123")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None
) -> User:
    if not authorization:
        # In development mode, fallback to demo user if no token provided
        if settings.APP_ENV == "development":
            return get_demo_user(db)
        raise UnauthorizedError("Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Invalid authorization format. Must be 'Bearer <token>'")

    token = parts[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise UnauthorizedError("Invalid or expired token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise UnauthorizedError("Invalid token subject")

    user = db.get(User, user_id)
    if not user:
        raise UnauthorizedError("User not found")
    return user
