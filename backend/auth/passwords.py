from __future__ import annotations

from functools import lru_cache

from passlib.context import CryptContext


@lru_cache()
def _get_password_context() -> CryptContext:
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    ctx = _get_password_context()
    return ctx.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    ctx = _get_password_context()
    try:
        return ctx.verify(plain_password, hashed_password)
    except ValueError:
        return False
