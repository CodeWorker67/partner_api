import json
import sqlite3
from typing import Optional

from config import DATABASE_PATH, DEFAULT_TRIAL_DAYS


DEFAULT_PRICES = {
    "m1_d3": 199,
    "m3_d3": 499,
    "m6_d3": 999,
    "m12_d3": 1188,
    "m1_d5": 299,
    "m3_d5": 749,
    "m6_d5": 1349,
    "m12_d5": 1799,
    "m1_d10": 659,
    "m3_d10": 1349,
    "m6_d10": 2399,
    "m12_d10": 3239,
}

_IDENTITY_COLUMNS = (
    ("partner_username", "TEXT"),
    ("bot_username", "TEXT"),
    ("bot_display_name", "TEXT"),
    ("source_bot_id", "BIGINT"),
)


def ensure_database_dir() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _ensure_identity_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(partner_bot_settings)")}
    for name, col_type in _IDENTITY_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE partner_bot_settings ADD COLUMN {name} {col_type}")


def init_partner_bot_settings(
    bot_id: int,
    owner_tg_id: int,
    *,
    partner_username: Optional[str] = None,
    bot_username: Optional[str] = None,
    bot_display_name: Optional[str] = None,
    source_bot_id: Optional[int] = None,
) -> None:
    """Создаёт/обновляет запись настроек бота при deploy."""
    ensure_database_dir()
    partner_username = (partner_username or "").lstrip("@") or None
    bot_username = (bot_username or "").lstrip("@") or None
    bot_display_name = (bot_display_name or "").strip() or None

    conn = sqlite3.connect(str(DATABASE_PATH))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS partner_bot_settings (
                bot_id INTEGER PRIMARY KEY,
                owner_tg_id BIGINT NOT NULL,
                partner_balance INTEGER DEFAULT 0,
                balance_own_bot INTEGER DEFAULT 0,
                balance_child_bots INTEGER DEFAULT 0,
                partner_pay INTEGER DEFAULT 0,
                channel_id BIGINT,
                channel_url TEXT,
                channel_required BOOLEAN DEFAULT 0,
                trial_days INTEGER DEFAULT 3,
                prices_json TEXT,
                partner_username TEXT,
                bot_username TEXT,
                bot_display_name TEXT,
                source_bot_id BIGINT
            )
            """
        )
        _ensure_identity_columns(conn)
        cur = conn.execute(
            "SELECT 1 FROM partner_bot_settings WHERE bot_id = ?",
            (bot_id,),
        )
        if cur.fetchone():
            # COALESCE: не затираем уже заполненные поля, если при redeploy поле не передали
            conn.execute(
                """
                UPDATE partner_bot_settings
                SET partner_username = COALESCE(?, partner_username),
                    bot_username = COALESCE(?, bot_username),
                    bot_display_name = COALESCE(?, bot_display_name),
                    source_bot_id = COALESCE(?, source_bot_id)
                WHERE bot_id = ?
                """,
                (partner_username, bot_username, bot_display_name, source_bot_id, bot_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO partner_bot_settings
                (bot_id, owner_tg_id, partner_balance, partner_pay, trial_days, prices_json,
                 partner_username, bot_username, bot_display_name, source_bot_id)
                VALUES (?, ?, 0, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bot_id,
                    owner_tg_id,
                    DEFAULT_TRIAL_DAYS,
                    json.dumps(DEFAULT_PRICES),
                    partner_username,
                    bot_username,
                    bot_display_name,
                    source_bot_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def list_existing_bot_ids() -> list[int]:
    ensure_database_dir()
    if not DATABASE_PATH.exists():
        return []
    conn = sqlite3.connect(str(DATABASE_PATH))
    try:
        try:
            rows = conn.execute(
                "SELECT bot_id FROM partner_bot_settings ORDER BY bot_id"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [int(r[0]) for r in rows]
    finally:
        conn.close()


def apply_identity_settings(
    items: list[dict],
    *,
    dry_run: bool = False,
) -> dict:
    """
    Обновляет identity-поля только для bot_id, которые уже есть в partner_bot_settings.
    items: [{bot_id, partner_username?, bot_username?, bot_display_name?, source_bot_id?}, ...]
    """
    ensure_database_dir()
    if not DATABASE_PATH.exists():
        return {
            "updated": 0,
            "skipped_missing": 0,
            "received": len(items),
            "existing_bot_ids": 0,
            "dry_run": dry_run,
            "preview": [],
        }

    conn = sqlite3.connect(str(DATABASE_PATH))
    try:
        try:
            _ensure_identity_columns(conn)
            conn.commit()
        except sqlite3.OperationalError:
            return {
                "updated": 0,
                "skipped_missing": len(items),
                "received": len(items),
                "existing_bot_ids": 0,
                "dry_run": dry_run,
                "preview": [],
                "error": "partner_bot_settings table missing",
            }

        existing = {
            int(r[0])
            for r in conn.execute("SELECT bot_id FROM partner_bot_settings").fetchall()
        }
        preview: list[dict] = []
        updates: list[tuple] = []
        skipped_missing = 0

        for raw in items:
            try:
                bot_id = int(raw["bot_id"])
            except (KeyError, TypeError, ValueError):
                skipped_missing += 1
                continue
            if bot_id not in existing:
                skipped_missing += 1
                continue

            partner_username = raw.get("partner_username")
            if isinstance(partner_username, str):
                partner_username = partner_username.lstrip("@") or None
            bot_username = raw.get("bot_username")
            if isinstance(bot_username, str):
                bot_username = bot_username.lstrip("@") or None
            bot_display_name = raw.get("bot_display_name")
            if isinstance(bot_display_name, str):
                bot_display_name = bot_display_name.strip() or None
            source_bot_id = raw.get("source_bot_id")
            if source_bot_id is not None:
                try:
                    source_bot_id = int(source_bot_id)
                except (TypeError, ValueError):
                    source_bot_id = None

            row = {
                "bot_id": bot_id,
                "partner_username": partner_username,
                "bot_username": bot_username,
                "bot_display_name": bot_display_name,
                "source_bot_id": source_bot_id,
            }
            preview.append(row)
            updates.append(
                (partner_username, bot_username, bot_display_name, source_bot_id, bot_id)
            )

        if not dry_run and updates:
            conn.executemany(
                """
                UPDATE partner_bot_settings
                SET partner_username = COALESCE(?, partner_username),
                    bot_username = COALESCE(?, bot_username),
                    bot_display_name = COALESCE(?, bot_display_name),
                    source_bot_id = COALESCE(?, source_bot_id)
                WHERE bot_id = ?
                """,
                updates,
            )
            conn.commit()

        return {
            "updated": len(updates),
            "skipped_missing": skipped_missing,
            "received": len(items),
            "existing_bot_ids": len(existing),
            "dry_run": dry_run,
            "preview": preview[:50],
        }
    finally:
        conn.close()


def get_bot_stats(bot_id: int) -> dict:
    ensure_database_dir()
    if not DATABASE_PATH.exists():
        return {"users_count": 0, "revenue": 0, "active_subscriptions": 0}

    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    try:
        users_count = 0
        active_subscriptions = 0
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE bot_id = ? AND is_delete = 0",
                (bot_id,),
            ).fetchone()
            users_count = row["c"] if row else 0
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM users
                WHERE bot_id = ? AND is_delete = 0
                  AND (subscription_end_date IS NOT NULL
                       OR subscription_3_end_date IS NOT NULL
                       OR subscription_10_end_date IS NOT NULL)
                """,
                (bot_id,),
            ).fetchone()
            active_subscriptions = row["c"] if row else 0
        except sqlite3.OperationalError:
            pass

        revenue = 0
        for table in (
            "payments_fk_sbp",
            "payments_stars",
            "payments_cryptobot",
        ):
            try:
                row = conn.execute(
                    f"""
                    SELECT COALESCE(SUM(amount), 0) AS s FROM {table}
                    WHERE bot_id = ? AND status = 'confirmed'
                    """,
                    (bot_id,),
                ).fetchone()
                if row:
                    revenue += int(row["s"] or 0)
            except sqlite3.OperationalError:
                continue

        balance = 0
        try:
            row = conn.execute(
                "SELECT partner_balance FROM partner_bot_settings WHERE bot_id = ?",
                (bot_id,),
            ).fetchone()
            if row:
                balance = int(row["partner_balance"] or 0)
        except sqlite3.OperationalError:
            pass

        return {
            "users_count": users_count,
            "active_subscriptions": active_subscriptions,
            "revenue": revenue,
            "partner_balance": balance,
        }
    finally:
        conn.close()
