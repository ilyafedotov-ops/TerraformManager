from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import pytest
from fastapi.testclient import TestClient

from api.main import app
from backend import storage
from backend.auth.tokens import TokenService
from backend.db.repositories import auth as auth_repo
from backend.db.session import get_session_dependency, init_models, session_scope


ProjectsClientFixture = Tuple[TestClient, str, Path, Path]


@pytest.fixture()
def projects_client(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[ProjectsClientFixture]:
    base_dir = tmp_path_factory.mktemp("projects_api")
    db_path = base_dir / "app.db"
    init_models(db_path)
    projects_root = base_dir / "projects"
    monkeypatch.setattr(storage, "DEFAULT_PROJECTS_ROOT", projects_root)

    def override_session_dependency():
        with session_scope(db_path) as session:
            yield session

    app.dependency_overrides[get_session_dependency] = override_session_dependency

    email = "api@example.com"
    password = "Str0ngPass!"
    token_service = TokenService()
    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read", "console:write"],
        )

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/auth/token",
                data={"username": email, "password": password, "scope": "console:read console:write"},
                headers={"Accept": "application/json"},
            )
            assert login_response.status_code == 200
            access_token = login_response.json()["access_token"]
            yield client, access_token, db_path, projects_root
    finally:
        app.dependency_overrides.pop(get_session_dependency, None)
