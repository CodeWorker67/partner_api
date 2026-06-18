import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config import REGISTRY_PATH


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BotRegistry:
    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, bot_id: int) -> Optional[Dict[str, Any]]:
        return self._read().get(str(bot_id))

    def upsert(
        self,
        bot_id: int,
        *,
        instance_id: str,
        partner_tg_id: int,
        bot_username: str,
        status: str,
        started_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self._read()
        key = str(bot_id)
        existing = data.get(key, {})
        record = {
            "bot_id": bot_id,
            "instance_id": instance_id,
            "partner_tg_id": partner_tg_id,
            "bot_username": bot_username,
            "status": status,
            "started_at": started_at or existing.get("started_at") or _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        data[key] = record
        self._write(data)
        return record

    def update_status(self, bot_id: int, status: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        key = str(bot_id)
        if key not in data:
            return None
        data[key]["status"] = status
        data[key]["updated_at"] = _utc_now_iso()
        self._write(data)
        return data[key]

    def list_all(self) -> Dict[str, Any]:
        return self._read()


registry = BotRegistry()
