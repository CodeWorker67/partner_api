import json
import sqlite3
from pathlib import Path

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


def ensure_database_dir() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_partner_bot_settings(bot_id: int, owner_tg_id: int) -> None:
    """Создаёт запись настроек бота при первом deploy (если таблица уже есть)."""
    ensure_database_dir()
    conn = sqlite3.connect(str(DATABASE_PATH))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS partner_bot_settings (
                bot_id INTEGER PRIMARY KEY,
                owner_tg_id BIGINT NOT NULL,
                partner_balance INTEGER DEFAULT 0,
                partner_pay INTEGER DEFAULT 0,
                channel_id BIGINT,
                channel_url TEXT,
                channel_required BOOLEAN DEFAULT 0,
                trial_days INTEGER DEFAULT 3,
                prices_json TEXT
            )
            """
        )
        cur = conn.execute(
            "SELECT 1 FROM partner_bot_settings WHERE bot_id = ?",
            (bot_id,),
        )
        if cur.fetchone():
            return
        conn.execute(
            """
            INSERT INTO partner_bot_settings
            (bot_id, owner_tg_id, partner_balance, partner_pay, trial_days, prices_json)
            VALUES (?, ?, 0, 0, ?, ?)
            """,
            (bot_id, owner_tg_id, DEFAULT_TRIAL_DAYS, json.dumps(DEFAULT_PRICES)),
        )
        conn.commit()
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
