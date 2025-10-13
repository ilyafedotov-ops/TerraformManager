from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


class Config(Base):
    __tablename__ = "configs"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="tfreview")
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    )

    def as_dict(self, include_payload: bool = True) -> Dict[str, Optional[str]]:
        payload_value = self.payload if include_payload else None
        return {
            "name": self.name,
            "kind": self.kind,
            "payload": payload_value,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    report: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.id,
            "summary": self.summary,
            "report": self.report,
            "created_at": format_timestamp(self.created_at),
        }


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    )

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": format_timestamp(self.updated_at),
        }


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scopes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    )

    refresh_sessions: Mapped[List["RefreshSession"]] = relationship(  # type: ignore[name-defined]
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    auth_events: Mapped[List["AuthAudit"]] = relationship(  # type: ignore[name-defined]
        back_populates="user",
        passive_deletes=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "scopes": list(self.scopes or []),
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


class RefreshSession(Base):
    __tablename__ = "auth_refresh_sessions"
    __table_args__ = (
        Index("ix_refresh_session_user_id_active", "user_id", "revoked_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_id: Mapped[str] = mapped_column(String, nullable=False, default=lambda: str(uuid4()), index=True)
    token_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    anti_csrf_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scopes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_sessions")
    audit_events: Mapped[List["AuthAudit"]] = relationship(  # type: ignore[name-defined]
        back_populates="session",
        passive_deletes=True,
    )

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(tz=timezone.utc)
        if self.revoked_at:
            return False
        return self.expires_at > now


class AuthAudit(Base):
    __tablename__ = "auth_audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(320), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, ForeignKey("auth_refresh_sessions.id", ondelete="SET NULL"), nullable=True)
    scopes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    user: Mapped[User | None] = relationship(back_populates="auth_events")
    session: Mapped[RefreshSession | None] = relationship(back_populates="audit_events")



def format_timestamp(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat(sep=" ")
