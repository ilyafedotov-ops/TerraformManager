import textwrap
from pathlib import Path
from types import SimpleNamespace

from backend.generators.docs import generate_docs


def test_generate_docs_creates_markdown(monkeypatch, tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    knowledge_dir = tmp_path / "knowledge"
    config_file = tmp_path / "config.yml"
    config_file.write_text("formatter: markdown table\n", encoding="utf-8")

    monkeypatch.setattr("backend.generators.docs.shutil.which", lambda _: "terraform-docs")

    def fake_run(command, check, capture_output, text):
        assert "markdown" in command
        return SimpleNamespace(stdout=textwrap.dedent(
            """
            ## Providers
            | Name |
            |------|
            | aws  |

            ## Inputs
            | Name | Description | Type | Default | Required |
            |------|-------------|------|---------|----------|
            | name | example     | any  | n/a     | no       |
            """
        ))

    monkeypatch.setattr("backend.generators.docs.subprocess.run", fake_run)
    monkeypatch.setattr("backend.generators.docs.warm_index", lambda: 42)

    result = generate_docs(
        output_dir=docs_dir,
        knowledge_dir=knowledge_dir,
        config_path=config_file,
        binary=None,
        reindex=True,
    )

    assert result["status"] == "ok"
    files = list(docs_dir.glob("*.md"))
    assert files, "expected at least one generated doc"
    knowledge_files = list(knowledge_dir.glob("*.md"))
    assert knowledge_files, "expected knowledge mirror files"
    assert result["indexed_documents"] == 42


def test_generate_docs_skips_when_cli_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.generators.docs.shutil.which", lambda _: None)
    result = generate_docs(output_dir=tmp_path, reindex=False)
    assert result["status"] == "skipped"
