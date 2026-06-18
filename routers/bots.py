from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import verify_api_key
from services.deployer import DeployError, bot_status, deploy_bot, restart_bot, stop_bot
from services.sqlite_init import get_bot_stats

router = APIRouter(prefix="/bots", tags=["bots"])


class DeployRequest(BaseModel):
    bot_id: int = Field(..., gt=0)
    token: str = Field(..., min_length=10)
    partner_tg_id: int = Field(..., gt=0)
    bot_username: str = Field(..., min_length=1)


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
        )
    except DeployError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
