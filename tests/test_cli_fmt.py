from pathlib import Path

from backend.cli import _collect_fmt_targets


def test_collect_fmt_targets_for_files_and_directories(tmp_path: Path) -> None:
    (tmp_path / "env").mkdir()
    file_a = tmp_path / "env" / "main.tf"
    file_a.write_text('resource "null_resource" "example" {}', encoding="utf-8")
    dir_b = tmp_path / "modules"
    dir_b.mkdir()

    targets = _collect_fmt_targets([file_a, dir_b])
    assert tmp_path / "env" in targets
    assert dir_b in targets
