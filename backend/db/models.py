from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
    Index,
    UniqueConstraint,
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
    __table_args__ = (
        Index("ix_reports_created_at", "created_at"),
        Index("ix_reports_review_status", "review_status"),
        Index("ix_reports_review_assignee", "review_assignee"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    report: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    review_assignee: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    review_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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

    comments: Mapped[List["ReportComment"]] = relationship(  # type: ignore[name-defined]
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.id,
            "summary": self.summary,
            "report": self.report,
            "review_status": self.review_status,
            "review_assignee": self.review_assignee,
            "review_due_at": format_timestamp(self.review_due_at),
            "review_notes": self.review_notes,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


class ReportComment(Base):
    __tablename__ = "report_comments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    report_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
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

    report: Mapped["Report"] = relationship(back_populates="comments")

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.id,
            "report_id": self.report_id,
            "author": self.author,
            "body": self.body,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
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


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    root_path: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
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

    runs: Mapped[List["ProjectRun"]] = relationship(  # type: ignore[name-defined]
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assets: Mapped[List["GeneratedAsset"]] = relationship(  # type: ignore[name-defined]
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    configs: Mapped[List["ProjectConfig"]] = relationship(  # type: ignore[name-defined]
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    artifacts: Mapped[List["ProjectArtifact"]] = relationship(  # type: ignore[name-defined]
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self, include_metadata: bool = True) -> Dict[str, Any]:
        payload = dict(self.project_metadata or {}) if include_metadata else None
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "root_path": self.root_path,
            "description": self.description,
            "metadata": payload,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


class ProjectRun(Base):
    __tablename__ = "project_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    triggered_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    artifacts_path: Mapped[str | None] = mapped_column(String, nullable=True)
    report_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="runs")
    report: Mapped[Report | None] = relationship()
    artifacts: Mapped[List["ProjectArtifact"]] = relationship(  # type: ignore[name-defined]
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self, include_parameters: bool = True, include_summary: bool = True) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "label": self.label,
            "kind": self.kind,
            "status": self.status,
            "triggered_by": self.triggered_by,
            "parameters": dict(self.parameters or {}) if include_parameters else None,
            "summary": dict(self.summary or {}) if include_summary else None,
            "artifacts_path": self.artifacts_path,
            "report_id": self.report_id,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
            "started_at": format_timestamp(self.started_at),
            "finished_at": format_timestamp(self.finished_at),
        }


class ProjectConfig(Base):
    __tablename__ = "project_configs"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_project_config_slug"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_name: Mapped[str | None] = mapped_column(String, ForeignKey("configs.name", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="tfreview")
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    config_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
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

    project: Mapped[Project] = relationship(back_populates="configs")
    config: Mapped[Config | None] = relationship()

    def to_dict(self, include_payload: bool = True) -> Dict[str, Any]:
        payload_value = self.payload if include_payload else None
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "config_name": self.config_name,
            "kind": self.kind,
            "payload": payload_value,
            "tags": list(self.tags or []),
            "metadata": dict(self.config_metadata or {}),
            "is_default": self.is_default,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


class ProjectArtifact(Base):
    __tablename__ = "project_artifacts"
    __table_args__ = (
        UniqueConstraint("project_id", "run_id", "relative_path", name="uq_project_artifact_path"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String, ForeignKey("project_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(String, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    relative_path: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(96), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    artifact_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
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

    project: Mapped[Project] = relationship(back_populates="artifacts")
    run: Mapped[ProjectRun | None] = relationship(back_populates="artifacts")
    report: Mapped[Report | None] = relationship()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "report_id": self.report_id,
            "name": self.name,
            "relative_path": self.relative_path,
            "storage_path": self.storage_path,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "tags": list(self.tags or []),
            "metadata": dict(self.artifact_metadata or {}),
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_type: Mapped[str] = mapped_column(String(48), nullable=False, default="artifact")
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    asset_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    latest_version_id: Mapped[str | None] = mapped_column(String, ForeignKey("generated_asset_versions.id", ondelete="SET NULL"), nullable=True)
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

    project: Mapped[Project] = relationship(back_populates="assets")
    versions: Mapped[List["GeneratedAssetVersion"]] = relationship(  # type: ignore[name-defined]
        "GeneratedAssetVersion",
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GeneratedAssetVersion.created_at.desc()",
        foreign_keys="GeneratedAssetVersion.asset_id",
    )
    latest_version: Mapped["GeneratedAssetVersion | None"] = relationship(  # type: ignore[name-defined]
        "GeneratedAssetVersion",
        primaryjoin="GeneratedAsset.latest_version_id == GeneratedAssetVersion.id",
        foreign_keys="GeneratedAsset.latest_version_id",
        post_update=True,
        uselist=False,
    )

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_generated_asset_project_name"),)

    def to_dict(self, include_versions: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "asset_type": self.asset_type,
            "tags": list(self.tags or []),
            "metadata": dict(self.asset_metadata or {}),
            "latest_version_id": self.latest_version_id,
            "created_at": format_timestamp(self.created_at),
            "updated_at": format_timestamp(self.updated_at),
        }
        if include_versions:
            payload["versions"] = [version.to_dict(include_blob=False) for version in self.versions]
        return payload


class GeneratedAssetVersion(Base):
    __tablename__ = "generated_asset_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("generated_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String, ForeignKey("project_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(String, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True, index=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    display_path: Mapped[str] = mapped_column(String, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(96), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    asset: Mapped[GeneratedAsset] = relationship(
        "GeneratedAsset",
        back_populates="versions",
        foreign_keys=[asset_id],
    )
    asset_latest: Mapped[GeneratedAsset] = relationship(
        "GeneratedAsset",
        back_populates="latest_version",
        primaryjoin="GeneratedAsset.latest_version_id == GeneratedAssetVersion.id",
        viewonly=True,
    )
    project: Mapped[Project] = relationship()
    run: Mapped[ProjectRun | None] = relationship()
    report: Mapped[Report | None] = relationship()

    def to_dict(self, include_blob: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "asset_id": self.asset_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "report_id": self.report_id,
            "storage_path": self.storage_path,
            "display_path": self.display_path,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "notes": self.notes,
            "created_at": format_timestamp(self.created_at),
        }
        if include_blob:
            payload["content"] = None
        return payload


def format_timestamp(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat(sep=" ")
