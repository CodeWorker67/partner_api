import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY: str = (os.environ.get("PARTNER_VPS_API_KEY") or "").strip()
API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("API_PORT", "8090"))

BOT_TEMPLATE_DIR: Path = Path(os.environ.get("BOT_TEMPLATE_DIR", "/root/bot_partner"))
INSTANCES_DIR: Path = Path(os.environ.get("INSTANCES_DIR", "/root"))
DATABASE_DIR: Path = Path(os.environ.get("DATABASE_DIR", "/root/database"))
DATABASE_PATH: Path = Path(os.environ.get("DATABASE_PATH", str(DATABASE_DIR / "partner.db")))
REGISTRY_PATH: Path = Path(os.environ.get("REGISTRY_PATH", "/root/partner_api/registry.json"))
SHARED_ENV_PATH: Path = Path(os.environ.get("SHARED_ENV_PATH", "/root/partner_api/shared.env"))

DEFAULT_TRIAL_DAYS: int = int(os.environ.get("DEFAULT_TRIAL_DAYS", "3"))
