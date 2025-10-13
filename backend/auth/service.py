from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.tokens import TokenService
from backend.db.repositories import auth as auth_repo


@dataclass
class AuthResult:
    user: auth_repo.User
    bundle: TokenService.TokenBundle  # type: ignore[attr-defined]


class AuthService:
    def __init__(self, token_service: TokenService | None = None):
        self._tokens = token_service or TokenService()

    def authenticate(self, session: Session, *, email: str, password: str, scopes: Sequence[str]) -> TokenService.TokenBundle:
        user = auth_repo.get_user_by_email(session, email)
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect credentials")
        if not self._tokens.verify_password(password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect credentials")

        return self._tokens.issue_tokens(session, user=user, scopes=scopes)

    def rotate(self, session: Session, *, refresh_token: str, anti_csrf: str | None):
        return self._tokens.rotate_refresh_token(session, refresh_token=refresh_token, anti_csrf_token=anti_csrf)

    def revoke(self, session: Session, *, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        try:
            payload = self._tokens.decode_refresh_token(refresh_token)
        except Exception:  # noqa: BLE001
            return
        session_id = payload.session_id
        if not session_id:
            return
        existing = auth_repo.get_refresh_session(session, session_id)
        if existing:
            self._tokens.revoke_session(session, existing, reason="logout")

