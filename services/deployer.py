import time

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import (
    BOT_TEMPLATE_DIR,
    DATABASE_PATH,
    INSTANCES_DIR,
    SHARED_ENV_PATH,
)
from services.registry import registry
from services.sqlite_init import init_partner_bot_settings


class DeployError(Exception):
    pass


def _service_name(bot_id: int) -> str:
    return f"partner-bot-{bot_id}"


def _instance_dir(bot_id: int) -> Path:
    return INSTANCES_DIR / str(bot_id)


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _systemctl_status(bot_id: int) -> str:
    name = _service_name(bot_id)
    try:
        result = _run(["systemctl", "is-active", name], check=False)
        out = (result.stdout or "").strip()
        if out == "active":
            return "running"
        if out in ("inactive", "failed"):
            return "stopped"
        return "error"
    except FileNotFoundError:
        return "error"


def _load_shared_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    if SHARED_ENV_PATH.exists():
        for line in SHARED_ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def _write_instance_env(
    bot_id: int,
    token: str,
    partner_tg_id: int,
    bot_username: str,
    shared: Dict[str, str],
    source_bot_id: Optional[int] = None,
) -> None:
    inst = _instance_dir(bot_id)
    lines = [
        f"TG_TOKEN={token}",
        f"BOT_ID={bot_id}",
        f"OWNER_TG_ID={partner_tg_id}",
        f"BOT_USERNAME={bot_username}",
        f"DATABASE_PATH={DATABASE_PATH}",
        f"BOT_URL=https://t.me/{bot_username}",
    ]
    if source_bot_id:
        lines.append(f"SOURCE_BOT_ID={source_bot_id}")
    skip = {"TG_TOKEN", "BOT_ID", "OWNER_TG_ID", "BOT_USERNAME", "DATABASE_PATH", "BOT_URL", "SOURCE_BOT_ID"}
    for key, val in shared.items():
        if key not in skip:
            lines.append(f"{key}={val}")
    (inst / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _create_venv(bot_id: int) -> None:
    inst = _instance_dir(bot_id)
    venv = inst / "venv"
    if not venv.exists():
        _run(["python3", "-m", "venv", str(venv)])
    req = inst / "requirements.txt"
    if req.exists():
        pip = venv / "bin" / "pip"
        _run([str(pip), "install", "-r", str(req), "-q"])


def _write_systemd_unit(bot_id: int) -> None:
    inst = _instance_dir(bot_id)
    name = _service_name(bot_id)
    unit = f"""[Unit]
Description=Partner VPN Bot {bot_id}
After=network.target

[Service]
Type=simple
WorkingDirectory={inst}
EnvironmentFile=-{inst / '.env'}
ExecStart={inst / 'venv' / 'bin' / 'python'} main.py
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    unit_path = Path(f"/etc/systemd/system/{name}.service")
    unit_path.write_text(unit, encoding="utf-8")
    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", name])


def deploy_bot(
    bot_id: int,
    token: str,
    partner_tg_id: int,
    bot_username: str,
    source_bot_id: Optional[int] = None,
    partner_username: Optional[str] = None,
    bot_display_name: Optional[str] = None,
) -> Dict[str, Any]:
    if not BOT_TEMPLATE_DIR.exists():
        raise DeployError(f"Bot template not found: {BOT_TEMPLATE_DIR}")

    inst = _instance_dir(bot_id)
    if inst.exists():
        shutil.rmtree(inst)
    shutil.copytree(BOT_TEMPLATE_DIR, inst, ignore=shutil.ignore_patterns("venv", "__pycache__", ".git", "logs", "*.db"))

    shared = _load_shared_env()
    _write_instance_env(bot_id, token, partner_tg_id, bot_username, shared, source_bot_id)
    _create_venv(bot_id)

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_partner_bot_settings(
        bot_id,
        partner_tg_id,
        partner_username=partner_username,
        bot_username=bot_username,
        bot_display_name=bot_display_name,
        source_bot_id=source_bot_id,
    )

    _write_systemd_unit(bot_id)
    name = _service_name(bot_id)
    _run(["systemctl", "restart", name], check=False)
    _run(["systemctl", "start", name])

    # Дать процессу стартовать; если сразу падает — status будет error/stopped
    time.sleep(2)
    status = _systemctl_status(bot_id)
    started_at = datetime.now(timezone.utc).isoformat()
    instance_id = f"{name}@{inst}"
    record = registry.upsert(
        bot_id,
        instance_id=instance_id,
        partner_tg_id=partner_tg_id,
        bot_username=bot_username,
        status=status,
        started_at=started_at,
        source_bot_id=source_bot_id,
    )
    return {
        "bot_id": bot_id,
        "instance_id": instance_id,
        "status": status,
        "started_at": started_at,
        "registry": record,
    }


def stop_bot(bot_id: int) -> Dict[str, Any]:
    name = _service_name(bot_id)
    _run(["systemctl", "stop", name], check=False)
    status = _systemctl_status(bot_id)
    registry.update_status(bot_id, status)
    return {"bot_id": bot_id, "status": status}


def restart_bot(bot_id: int) -> Dict[str, Any]:
    name = _service_name(bot_id)
    _run(["systemctl", "restart", name], check=False)
    status = _systemctl_status(bot_id)
    registry.update_status(bot_id, status)
    return {"bot_id": bot_id, "status": status}


def bot_status(bot_id: int) -> Dict[str, Any]:
    status = _systemctl_status(bot_id)
    record = registry.get(bot_id)
    return {
        "bot_id": bot_id,
        "status": status,
        "instance_id": record.get("instance_id") if record else None,
        "started_at": record.get("started_at") if record else None,
    }
