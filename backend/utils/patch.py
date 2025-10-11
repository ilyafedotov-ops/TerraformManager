from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any


@dataclass
class PatchFragment:
    file: str
    diff: str


def collect_patches(findings: Iterable[Dict[str, Any]]) -> List[PatchFragment]:
    patches: List[PatchFragment] = []
    for finding in findings:
        diff = finding.get("unified_diff")
        if not diff:
            continue
        file_path = finding.get("file")
        if not file_path:
            continue
        patches.append(PatchFragment(file=str(file_path), diff=diff))
    return patches


def format_patch_bundle(patches: List[PatchFragment]) -> str:
    return "\n\n".join(p.diff.rstrip() for p in patches if p.diff)
