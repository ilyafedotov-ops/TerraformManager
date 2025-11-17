#!/usr/bin/env python3
"""Service management utility for TerraformManager."""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
LOG_DIR = ROOT / "logs"
STATE_DIR = LOG_DIR / "service-manager"
DEFAULT_HOST = "0.0.0.0"


def _load_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        data[key.strip()] = value
    return data


BASE_ENV = os.environ.copy()
BASE_ENV.update(_load_env_file(ENV_FILE))


def _ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _kill_process(pid: int) -> None:
    try:
        if os.name != "nt":
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _read_json(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, str]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((DEFAULT_HOST, port))
        except OSError:
            return True
    return False


def _ensure_port_available(port: int) -> None:
    if not _port_in_use(port):
        return
    lsof = shutil.which("lsof")
    if lsof:
        try:
            result = subprocess.run(
                [lsof, "-ti", f"tcp:{port}"],
                capture_output=True,
                text=True,
                check=False,
            )
            pids = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        except Exception:
            pids = set()
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                continue
        if pids:
            time.sleep(1)
    if _port_in_use(port):
        raise RuntimeError(f"Port {port} is busy; stop the conflicting process and retry.")


@dataclass
class Service:
    name: str
    workdir: Path
    log_file: Path
    pid_file: Path
    build_command: Callable[[Dict[str, str]], List[str]]
    port_env: Optional[List[str]] = None
    default_port: Optional[int] = None

    def status(self) -> Dict[str, Optional[str]]:
        meta = _read_json(self.pid_file)
        pid = meta.get("pid")
        running = False
        if pid:
            try:
                running = _pid_is_running(int(pid))
            except ValueError:
                running = False
        return {
            "running": running,
            "pid": pid,
            "started_at": meta.get("started_at"),
            "log": str(self.log_file),
        }

    def start(self, env: Dict[str, str]) -> None:
        status = self.status()
        if status["running"]:
            print(f"{self.name}: already running (PID {status['pid']})")
            return
        port = self._resolve_port(env)
        if port:
            _ensure_port_available(port)
        cmd = self.build_command(env)
        log_handle = self.log_file.open("a", encoding="utf-8")
        start_new_session = os.name != "nt"
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.workdir),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=start_new_session,
            creationflags=creationflags,
        )
        _write_json(
            self.pid_file,
            {
                "pid": str(proc.pid),
                "started_at": _timestamp(),
                "command": " ".join(cmd),
            },
        )
        print(f"{self.name}: started (PID {proc.pid})")

    def stop(self) -> None:
        meta = _read_json(self.pid_file)
        pid_str = meta.get("pid")
        if not pid_str:
            print(f"{self.name}: not running")
            return
        try:
            pid = int(pid_str)
        except ValueError:
            print(f"{self.name}: invalid PID metadata; removing state")
            self.pid_file.unlink(missing_ok=True)
            return
        if not _pid_is_running(pid):
            print(f"{self.name}: process {pid} already stopped")
            self.pid_file.unlink(missing_ok=True)
            return
        print(f"{self.name}: stopping PID {pid}")
        _kill_process(pid)
        timeout = 10
        for _ in range(timeout * 10):
            if not _pid_is_running(pid):
                break
            time.sleep(0.1)
        else:
            print(f"{self.name}: process did not terminate in {timeout}s; sending SIGKILL")
            try:
                if os.name != "nt":
                    os.killpg(pid, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.pid_file.unlink(missing_ok=True)
        print(f"{self.name}: stopped")

    def _resolve_port(self, env: Dict[str, str]) -> Optional[int]:
        if not self.port_env:
            return self.default_port
        for key in self.port_env:
            value = env.get(key)
            if value and value.isdigit():
                return int(value)
        return self.default_port


def _resolve_python() -> str:
    candidate = ROOT / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    if sys.platform == "win32":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _build_api_command(env: Dict[str, str]) -> List[str]:
    return [_resolve_python(), "-m", "api"]


def _build_frontend_command(env: Dict[str, str]) -> List[str]:
    port = env.get("FRONTEND_PORT", "5173")
    host = env.get("FRONTEND_HOST", DEFAULT_HOST)
    pnpm = shutil.which("pnpm")
    if pnpm:
        return [pnpm, "run", "dev", "--", "--host", host, "--port", port]
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("Neither pnpm nor npm is available on PATH")
    return [npm, "run", "dev", "--", "--", "--host", host, "--port", port]

SERVICES: Dict[str, Service] = {
    "api": Service(
        name="api",
        workdir=ROOT,
        log_file=LOG_DIR / "api-service.log",
        pid_file=STATE_DIR / "api.pid.json",
        build_command=_build_api_command,
        port_env=["TFM_PORT", "PORT"],
        default_port=8890,
    ),
    "frontend": Service(
        name="frontend",
        workdir=ROOT / "frontend",
        log_file=LOG_DIR / "frontend-service.log",
        pid_file=STATE_DIR / "frontend.pid.json",
        build_command=_build_frontend_command,
        port_env=["FRONTEND_PORT"],
        default_port=5173,
    ),
}


def _select_services(target: str) -> Iterable[Service]:
    if target == "all":
        return SERVICES.values()
    return [SERVICES[target]]


def cmd_start(args: argparse.Namespace) -> None:
    env = BASE_ENV.copy()
    for svc in _select_services(args.service):
        try:
            svc.start(env)
        except Exception as exc:  # noqa: BLE001
            print(f"{svc.name}: failed to start ({exc})", file=sys.stderr)


def cmd_stop(args: argparse.Namespace) -> None:
    for svc in _select_services(args.service):
        svc.stop()


def cmd_status(_args: argparse.Namespace) -> None:
    for svc in SERVICES.values():
        state = svc.status()
        running = "running" if state["running"] else "stopped"
        extra = f"PID {state['pid']}" if state["pid"] else "no PID"
        print(f"{svc.name:<8} {running:<8} {extra:<12} log={state['log']}")


def _read_last_lines(path: Path, lines: int) -> List[str]:
    from collections import deque

    dq: deque[str] = deque(maxlen=lines)
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            dq.append(line.rstrip("\n"))
    return list(dq)


def _follow_file(path: Path) -> None:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.5)
                continue
            sys.stdout.write(line)
            sys.stdout.flush()


def cmd_logs(args: argparse.Namespace) -> None:
    svc = SERVICES[args.service]
    if not svc.log_file.exists():
        print(f"{svc.name}: log file {svc.log_file} does not exist")
        return
    if args.follow:
        print(f"Tailing {svc.log_file} (Ctrl+C to stop)...")
        try:
            _follow_file(svc.log_file)
        except KeyboardInterrupt:
            pass
        return
    tail_lines = _read_last_lines(svc.log_file, args.lines)
    for line in tail_lines:
        print(line)


def cmd_restart(args: argparse.Namespace) -> None:
    cmd_stop(args)
    time.sleep(0.5)
    cmd_start(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage TerraformManager services")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Start one or more services")
    start.add_argument("service", choices=["api", "frontend", "all"], help="Target service")
    start.set_defaults(func=cmd_start)

    stop = sub.add_parser("stop", help="Stop one or more services")
    stop.add_argument("service", choices=["api", "frontend", "all"], help="Target service")
    stop.set_defaults(func=cmd_stop)

    restart = sub.add_parser("restart", help="Restart a service")
    restart.add_argument("service", choices=["api", "frontend", "all"], help="Target service")
    restart.set_defaults(func=cmd_restart)

    status = sub.add_parser("status", help="Display service status")
    status.set_defaults(func=cmd_status)

    logs = sub.add_parser("logs", help="Show service logs")
    logs.add_argument("service", choices=list(SERVICES.keys()), help="Target service")
    logs.add_argument("--lines", type=int, default=40, help="Number of log lines to print")
    logs.add_argument("--follow", action="store_true", help="Stream log output")
    logs.set_defaults(func=cmd_logs)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    _ensure_dirs()
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
