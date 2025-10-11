from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


DEFAULT_DEST = Path("knowledge/external")


@dataclass
class SyncResult:
    source: str
    dest_dir: Path
    files: List[Path]
    note: Optional[str] = None


def _gh_zip_url(repo_url: str) -> Optional[str]:
    # Accept forms like https://github.com/<owner>/<repo>[/tree/<branch>]
    try:
        if "github.com" not in repo_url:
            return None
        parts = repo_url.strip("/").split("/")
        # https://github.com/owner/repo
        if len(parts) < 5:
            owner = parts[-2]
            repo = parts[-1]
            branch = "main"
        else:
            owner = parts[-4]
            repo = parts[-3]
            # e.g., tree/main
            branch = parts[-1]
        return f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
    except Exception:
        return None


def _safe_extract_md(zf: zipfile.ZipFile, dest: Path) -> List[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    prefix = None
    # Find the common top-level folder
    for name in zf.namelist():
        if name.endswith("/"):
            prefix = name.split("/")[0]
            break
    for name in zf.namelist():
        if not name.lower().endswith(".md"):
            continue
        # Strip the leading prefix folder if present
        rel_name = name
        if prefix and rel_name.startswith(prefix):
            rel_name = rel_name[len(prefix) + 1 :]
        target = dest / rel_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(name, "r") as src, target.open("wb") as out:
            out.write(src.read())
        saved.append(target)
    return saved


def sync_github_repo(repo_url: str, dest_root: Path = DEFAULT_DEST) -> SyncResult:
    dest_root.mkdir(parents=True, exist_ok=True)
    zip_url = _gh_zip_url(repo_url)
    note = None
    if not zip_url:
        raise ValueError(f"Unsupported GitHub URL: {repo_url}")
    try:
        with urlopen(zip_url) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            repo_name = repo_url.rstrip("/").split("/")[-1]
            dest_dir = dest_root / repo_name
            files = _safe_extract_md(zf, dest_dir)
            return SyncResult(source=repo_url, dest_dir=dest_dir, files=files, note=note)
    except HTTPError as e:
        # Retry with master branch if main not found
        if e.code == 404 and zip_url.endswith("/main"):
            alt = zip_url[:-5] + "master"
            with urlopen(alt) as resp:
                data = resp.read()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                repo_name = repo_url.rstrip("/").split("/")[-1]
                dest_dir = dest_root / repo_name
                files = _safe_extract_md(zf, dest_dir)
                note = "Fetched from master branch"
                return SyncResult(source=repo_url, dest_dir=dest_dir, files=files, note=note)
        raise


def sync_many(sources: Iterable[str], dest_root: Path = DEFAULT_DEST) -> List[SyncResult]:
    results: List[SyncResult] = []
    for src in sources:
        try:
            results.append(sync_github_repo(src, dest_root=dest_root))
        except Exception as exc:
            results.append(SyncResult(source=src, dest_dir=dest_root, files=[], note=f"error: {exc}"))
    return results

