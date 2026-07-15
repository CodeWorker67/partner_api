"""Клиент API мастер-бота (Zoomer) для pull identity-настроек."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import httpx

from config import MASTER_BOT_API_KEY, MASTER_BOT_API_TIMEOUT, MASTER_BOT_API_URL


class MasterApiError(Exception):
    pass


def _headers() -> Dict[str, str]:
    if not MASTER_BOT_API_KEY:
        raise MasterApiError("MASTER_BOT_API_KEY not configured")
    return {
        "X-Partner-Bot-Api-Key": MASTER_BOT_API_KEY,
        "Accept": "application/json",
    }


async def fetch_application_settings(
    bot_ids: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    if not MASTER_BOT_API_URL:
        raise MasterApiError("MASTER_BOT_API_URL not configured")

    url = f"{MASTER_BOT_API_URL}/api/partner/applications/settings"
    params: Dict[str, str] = {}
    if bot_ids:
        params["ids"] = ",".join(str(i) for i in bot_ids)

    timeout = httpx.Timeout(MASTER_BOT_API_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=_headers(), params=params or None)
        try:
            data = resp.json()
        except Exception as e:
            raise MasterApiError(f"invalid JSON from master: HTTP {resp.status_code}") from e
        if resp.status_code >= 400:
            raise MasterApiError(str(data.get("detail", data)))
        items = data.get("items")
        if not isinstance(items, list):
            raise MasterApiError("master response missing items[]")
        return items
