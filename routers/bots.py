from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import verify_api_key
from services.deployer import DeployError, bot_status, deploy_bot, restart_bot, stop_bot
from services.master_client import MasterApiError, fetch_application_settings
from services.sqlite_init import (
    apply_identity_settings,
    get_bot_stats,
    list_existing_bot_ids,
)

router = APIRouter(prefix="/bots", tags=["bots"])


class DeployRequest(BaseModel):
    bot_id: int = Field(..., gt=0)
    token: str = Field(..., min_length=10)
    partner_tg_id: int = Field(..., gt=0)
    bot_username: str = Field(..., min_length=1)
    source_bot_id: int | None = Field(None, gt=0)
    partner_username: str | None = Field(None)
    bot_display_name: str | None = Field(None)


class SettingsItem(BaseModel):
    bot_id: int = Field(..., gt=0)
    partner_username: Optional[str] = None
    bot_username: Optional[str] = None
    bot_display_name: Optional[str] = None
    source_bot_id: Optional[int] = None


class SettingsSyncRequest(BaseModel):
    items: list[SettingsItem] = Field(default_factory=list)
    dry_run: bool = False


class PullFromMasterRequest(BaseModel):
    dry_run: bool = False
    only_existing: bool = True


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/deploy", dependencies=[Depends(verify_api_key)])
async def deploy(req: DeployRequest):
    try:
        return deploy_bot(
            req.bot_id,
            req.token,
            req.partner_tg_id,
            req.bot_username.lstrip("@"),
            source_bot_id=req.source_bot_id,
            partner_username=req.partner_username,
            bot_display_name=req.bot_display_name,
        )
    except DeployError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/settings/sync", dependencies=[Depends(verify_api_key)])
async def settings_sync(req: SettingsSyncRequest) -> dict[str, Any]:
    """Принимает identity-поля с мастера и пишет в partner.db (только существующие bot_id)."""
    items = [i.model_dump() for i in req.items]
    return apply_identity_settings(items, dry_run=req.dry_run)


@router.post("/settings/pull-from-master", dependencies=[Depends(verify_api_key)])
async def settings_pull_from_master(req: PullFromMasterRequest) -> dict[str, Any]:
    """
    Тянет identity-поля с API мастер-бота и обновляет локальную partner.db.
    Нужны MASTER_BOT_API_URL и MASTER_BOT_API_KEY в .env partner_api.

    По умолчанию запрашивает у мастера только bot_id, которые уже есть локально.
    Если локальных id много (>80) — забирает полный список с мастера и фильтрует локально.
    """
    existing = list_existing_bot_ids()
    if req.only_existing and not existing:
        return {
            "updated": 0,
            "skipped_missing": 0,
            "received": 0,
            "existing_bot_ids": 0,
            "dry_run": req.dry_run,
            "preview": [],
            "detail": "В partner_bot_settings нет bot_id",
        }

    try:
        # длинный ?ids=... режем; apply_identity_settings всё равно обновит только existing
        bot_ids = None
        if req.only_existing and len(existing) <= 80:
            bot_ids = existing
        items = await fetch_application_settings(bot_ids)
    except MasterApiError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    result = apply_identity_settings(items, dry_run=req.dry_run)
    result["fetched_from_master"] = len(items)
    return result


@router.post("/{bot_id}/stop", dependencies=[Depends(verify_api_key)])
async def stop(bot_id: int):
    return stop_bot(bot_id)


@router.post("/{bot_id}/restart", dependencies=[Depends(verify_api_key)])
async def restart(bot_id: int):
    return restart_bot(bot_id)


@router.get("/{bot_id}/status", dependencies=[Depends(verify_api_key)])
async def status(bot_id: int):
    return bot_status(bot_id)


@router.get("/{bot_id}/stats", dependencies=[Depends(verify_api_key)])
async def stats(bot_id: int):
    base = bot_status(bot_id)
    base.update(get_bot_stats(bot_id))
    return base
