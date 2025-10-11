import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from backend.policies.helpers import make_candidate

def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run_terraform_validate(paths: List[Path]) -> List[Dict[str, Any]]:
    """If terraform is installed, attempt a basic validate in a temp dir.
    We copy .tf files only; no backend/state operations are performed.
    """
    if not which("terraform"):
        return []
    tmp = Path(tempfile.mkdtemp(prefix="tf-validate-"))
    # copy .tf files to tmp
    for p in paths:
        if p.is_dir():
            for tf in p.rglob("*.tf"):
                _cp(tf, tmp / tf.name)
        elif p.suffix == ".tf":
            _cp(p, tmp / p.name)
    findings: List[Dict[str, Any]] = []
    try:
        # init without backend
        subprocess.run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], cwd=tmp, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        proc = subprocess.run(["terraform", "validate", "-no-color"], cwd=tmp, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            origin = paths[0] if paths else tmp
            findings.append(
                make_candidate(
                    "SYNTAX-TERRAFORM-VALIDATE",
                    Path(origin),
                    line=1,
                    context={"file": str(origin)},
                    snippet=proc.stdout[:1000] if proc.stdout else "",
                    unique_id="SYNTAX-TERRAFORM-VALIDATE::terraform-validate",
                )
            )
    except Exception:
        pass
    return findings

def _cp(src: Path, dst: Path):
    dst.write_bytes(src.read_bytes())
