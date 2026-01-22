import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

DB_NAME = "mining_farm.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        try:
            self.cursor.execute("PRAGMA journal_mode=WAL")
            self.cursor.execute("PRAGMA synchronous=NORMAL")
            self.cursor.execute("PRAGMA foreign_keys=ON")
            self.conn.commit()
        except Exception:
            pass

        self.init_db()
        self._migrate_wallet_address_columns()


    def _migrate_wallet_address_columns(self) -> None:
        try:
            cols = [str(r[1]) for r in self.cursor.execute("PRAGMA table_info(users)").fetchall()]
        except Exception:
            return

        if "usd_address" not in cols:
            return

        legacy_cols = [c for c in cols if c.endswith("_address") and c not in ("usd_address", "btc_address")]
        if not legacy_cols:
            return

        legacy_col = legacy_cols[0]
        try:
            self.cursor.execute(
                f"UPDATE users SET usd_address = COALESCE(usd_address, {legacy_col}) WHERE usd_address IS NULL OR usd_address = ''"
            )
            self.conn.commit()
        except Exception:
            pass

    def init_db(self):
                               
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                bitcoin_balance REAL DEFAULT 0,
                -- Суммарные характеристики фермы
                total_hashrate REAL DEFAULT 0,
                total_power_consumption REAL DEFAULT 0,
                total_heat_generation REAL DEFAULT 0,
                total_psu_power REAL DEFAULT 0,
                total_cooling_efficiency REAL DEFAULT 0,
                pending_bitcoin REAL DEFAULT 0,
                last_collect_time TIMESTAMP,
                -- Служебные поля
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bank_balance REAL DEFAULT 0,
                bank_bitcoin_balance REAL DEFAULT 0,
                usd_address TEXT,
                btc_address TEXT,
                -- Система пыли
                dust_level REAL DEFAULT 0,
                dust_last_update TIMESTAMP
            )
        """)
        
                                                         
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN bitcoin_balance REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN pending_bitcoin REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN mining_enabled INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN bank_balance REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN bank_bitcoin_balance REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN usd_address TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN btc_address TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN last_report_time TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass
                                
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN dust_level REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN dust_last_update TIMESTAMP")
        except sqlite3.OperationalError:
            pass

                                                                                                   
                                             
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT,
                title TEXT,
                username TEXT,
                invite_link TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        try:
            self.cursor.execute("ALTER TABLE chats ADD COLUMN username TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE chats ADD COLUMN invite_link TEXT")
        except sqlite3.OperationalError:
            pass

                                          
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

                                                                         
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id TEXT,
                item_name TEXT,
                item_type TEXT,
                quantity INTEGER DEFAULT 1,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                wear REAL DEFAULT 100.0,
                is_broken INTEGER DEFAULT 0,
                unique_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
                                                        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS installed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id TEXT,
                item_name TEXT,
                item_type TEXT,
                quantity INTEGER DEFAULT 1,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                wear REAL DEFAULT 100.0,
                unique_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
                                                               
        try:
            self.cursor.execute("ALTER TABLE inventory ADD COLUMN wear REAL DEFAULT 100.0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE inventory ADD COLUMN is_broken INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE inventory ADD COLUMN unique_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE installed_items ADD COLUMN wear REAL DEFAULT 100.0")
        except sqlite3.OperationalError:
            pass
        try:
            self.cursor.execute("ALTER TABLE installed_items ADD COLUMN unique_id TEXT")
        except sqlite3.OperationalError:
            pass
                                                                             
        try:
            self.cursor.execute("UPDATE inventory SET wear = 100.0 WHERE wear IS NULL")
            self.cursor.execute("UPDATE installed_items SET wear = 100.0 WHERE wear IS NULL")
            self.cursor.execute("UPDATE inventory SET is_broken = 0 WHERE is_broken IS NULL")
        except sqlite3.OperationalError:
            pass
                                                                
        try:
            self.cursor.execute("ALTER TABLE chats ADD COLUMN title TEXT")
        except sqlite3.OperationalError:
            pass

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clans (
                clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                leader_id INTEGER NOT NULL,
                treasury_usd REAL DEFAULT 0,
                reputation INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        try:
            self.cursor.execute("ALTER TABLE clans ADD COLUMN treasury_usd REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            clan_cols = [str(r[1]) for r in self.cursor.execute("PRAGMA table_info(clans)").fetchall()]
            if "treasury_usd" in clan_cols:
                legacy = [c for c in clan_cols if c.startswith("treasury_") and c != "treasury_usd"]
                if legacy:
                    legacy_col = legacy[0]
                    self.cursor.execute(
                        f"UPDATE clans SET treasury_usd = CASE WHEN treasury_usd IS NULL OR treasury_usd = 0 THEN {legacy_col} ELSE treasury_usd END"
                    )
        except Exception:
            pass

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clan_members (
                clan_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (clan_id, user_id),
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clan_invites (
                token TEXT PRIMARY KEY,
                clan_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                invitee_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clan_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                actor_user_id INTEGER,
                event_type TEXT NOT NULL,
                amount_usd REAL,
                meta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clan_active_bonuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_id INTEGER NOT NULL,
                bonus_key TEXT NOT NULL,
                percent REAL NOT NULL DEFAULT 0,
                expires_at TIMESTAMP NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE
            )
            """
        )

        try:
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_clan_invites_invitee ON clan_invites(invitee_id)")
        except sqlite3.OperationalError:
            pass

        try:
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id)")
        except sqlite3.OperationalError:
            pass

        try:
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_clan_events_clan ON clan_events(clan_id, created_at DESC)")
        except sqlite3.OperationalError:
            pass

        try:
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_clan_bonuses_clan ON clan_active_bonuses(clan_id, expires_at)")
        except sqlite3.OperationalError:
            pass

        self.conn.commit()

    def get_clan_for_user(self, user_id: int) -> Optional[Dict]:
        self.cursor.execute(
            """
            SELECT
                c.clan_id,
                c.name,
                c.leader_id,
                c.treasury_usd,
                c.reputation,
                c.created_at,
                m.role AS member_role,
                m.joined_at AS joined_at
            FROM clan_members m
            JOIN clans c ON c.clan_id = m.clan_id
            WHERE m.user_id = ?
            """,
            (user_id,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_clan_member_count(self, clan_id: int) -> int:
        self.cursor.execute("SELECT COUNT(*) AS cnt FROM clan_members WHERE clan_id = ?", (clan_id,))
        row = self.cursor.fetchone()
        if not row:
            return 0
        return int(row["cnt"] or 0)

    def get_top_clan_by_treasury(self) -> Optional[Dict]:
        self.cursor.execute(
            """
            SELECT
                c.clan_id,
                c.name,
                c.leader_id,
                c.treasury_usd,
                u.username AS leader_username
            FROM clans c
            LEFT JOIN users u ON u.user_id = c.leader_id
            ORDER BY c.treasury_usd DESC
            LIMIT 1
            """
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def create_clan(self, leader_id: int, name: str, creation_cost_usd: int) -> Tuple[bool, str, Optional[int]]:
        clan_name = (name or "").strip()
        if not clan_name:
            return False, "❌ Укажите название клана.", None
        if len(clan_name) > 32:
            return False, "❌ Название клана слишком длинное (максимум 32 символа).", None

        user = self.get_user(int(leader_id))
        if not user:
            return False, "❌ Сначала зарегистрируйтесь: /mining", None

        existing = self.get_clan_for_user(int(leader_id))
        if existing:
            return False, "❌ Вы уже состоите в клане.", None

        balance = float(user.get("balance", 0) or 0)
        if balance < float(creation_cost_usd):
            return False, f"❌ Недостаточно средств. Нужно: {int(creation_cost_usd)} USD.", None

        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "INSERT INTO clans (name, leader_id) VALUES (?, ?)",
                (clan_name, int(leader_id)),
            )
            clan_id = int(self.cursor.lastrowid)
            self.cursor.execute(
                "INSERT INTO clan_members (clan_id, user_id, role) VALUES (?, ?, ?)",
                (clan_id, int(leader_id), "leader"),
            )
            self.cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (float(creation_cost_usd), int(leader_id)),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, NULL, ?)",
                (clan_id, int(leader_id), "clan_created", clan_name),
            )
            self.conn.commit()
            return True, "✅ Клан создан!", clan_id
        except sqlite3.IntegrityError:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Клан с таким названием уже существует.", None
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось создать клан. Попробуйте позже.", None

    def create_clan_invite(
        self,
        clan_id: int,
        inviter_id: int,
        invitee_id: int,
        *,
        expires_in_hours: int = 24,
    ) -> Tuple[bool, str, Optional[str]]:
        if int(inviter_id) == int(invitee_id):
            return False, "❌ Нельзя пригласить самого себя.", None

        clan = self.get_clan_for_user(int(inviter_id))
        if not clan or int(clan.get("clan_id", 0) or 0) != int(clan_id):
            return False, "❌ Вы не состоите в этом клане.", None

        if str(clan.get("member_role")) != "leader":
            return False, "❌ Приглашать может только глава клана.", None

        if self.get_clan_for_user(int(invitee_id)):
            return False, "❌ Игрок уже состоит в клане.", None

        expires_at = datetime.utcnow() + timedelta(hours=int(expires_in_hours))
        token = secrets.token_hex(8)

        try:
            self.cursor.execute(
                "UPDATE clan_invites SET status = 'expired' WHERE invitee_id = ? AND status = 'pending'",
                (int(invitee_id),),
            )
        except Exception:
            pass

        try:
            self.cursor.execute(
                """
                INSERT INTO clan_invites (token, clan_id, inviter_id, invitee_id, status, expires_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (token, int(clan_id), int(inviter_id), int(invitee_id), expires_at),
            )
            self.conn.commit()
            return True, "✅ Приглашение создано.", token
        except sqlite3.IntegrityError:
            return False, "❌ Не удалось создать приглашение. Попробуйте ещё раз.", None
        except Exception:
            return False, "❌ Не удалось создать приглашение. Попробуйте позже.", None

    def accept_clan_invite(self, token: str, user_id: int) -> Tuple[bool, str, Optional[int]]:
        token_str = (token or "").strip()
        if not token_str:
            return False, "❌ Приглашение недействительно.", None

        self.cursor.execute("SELECT * FROM clan_invites WHERE token = ?", (token_str,))
        invite_row = self.cursor.fetchone()
        if not invite_row:
            return False, "❌ Приглашение не найдено.", None
        invite = dict(invite_row)

        if str(invite.get("status")) != "pending":
            return False, "❌ Это приглашение уже неактуально.", None

        invitee_id = int(invite.get("invitee_id") or 0)
        if int(invitee_id) != int(user_id):
            return False, "❌ Это приглашение не для вас.", None

        expires_at = invite.get("expires_at")
        if isinstance(expires_at, str) and expires_at.strip():
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except ValueError:
                expires_at = None

        if isinstance(expires_at, datetime):
            if datetime.utcnow() > expires_at:
                try:
                    self.cursor.execute("UPDATE clan_invites SET status = 'expired' WHERE token = ?", (token_str,))
                    self.conn.commit()
                except Exception:
                    pass
                return False, "❌ Приглашение истекло.", None

        if self.get_clan_for_user(int(user_id)):
            return False, "❌ Вы уже состоите в клане.", None

        clan_id = int(invite.get("clan_id") or 0)
        self.cursor.execute("SELECT 1 FROM clans WHERE clan_id = ?", (clan_id,))
        if not self.cursor.fetchone():
            try:
                self.cursor.execute("UPDATE clan_invites SET status = 'expired' WHERE token = ?", (token_str,))
                self.conn.commit()
            except Exception:
                pass
            return False, "❌ Клан больше не существует.", None

        try:
            if not self.get_user(int(user_id)):
                self.create_user(int(user_id), None)
        except Exception:
            pass

        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "INSERT INTO clan_members (clan_id, user_id, role) VALUES (?, ?, 'member')",
                (clan_id, int(user_id)),
            )
            self.cursor.execute(
                "UPDATE clan_invites SET status = 'accepted' WHERE token = ?",
                (token_str,),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, NULL, NULL)",
                (clan_id, int(user_id), "member_join"),
            )
            self.conn.commit()
            return True, "✅ Вы вступили в клан!", clan_id
        except sqlite3.IntegrityError:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось вступить в клан (возможно, вы уже в клане).", None
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось вступить в клан. Попробуйте позже.", None

    def add_clan_event(
        self,
        clan_id: int,
        actor_user_id: Optional[int],
        event_type: str,
        amount_usd: Optional[float] = None,
        meta: Optional[str] = None,
    ) -> None:
        try:
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, ?, ?)",
                (int(clan_id), int(actor_user_id) if actor_user_id is not None else None, str(event_type), amount_usd, meta),
            )
            self.conn.commit()
        except Exception:
            pass

    def get_clan_events(self, clan_id: int, limit: int = 20) -> list[Dict]:
        self.cursor.execute(
            "SELECT * FROM clan_events WHERE clan_id = ? ORDER BY id DESC LIMIT ?",
            (int(clan_id), int(limit)),
        )
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    def get_clan_active_bonuses(self, clan_id: int, limit: int = 20) -> list[Dict]:
        now = datetime.utcnow()
        self.cursor.execute(
            """
            SELECT *
            FROM clan_active_bonuses
            WHERE clan_id = ? AND expires_at > ?
            ORDER BY expires_at ASC
            LIMIT ?
            """,
            (int(clan_id), now, int(limit)),
        )
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    def get_clan_hashrate_bonus_percent(self, clan_id: int) -> float:
        now = datetime.utcnow()
        self.cursor.execute(
            "SELECT COALESCE(SUM(percent), 0) AS total FROM clan_active_bonuses WHERE clan_id = ? AND expires_at > ?",
            (int(clan_id), now),
        )
        row = self.cursor.fetchone()
        return float((row["total"] if row else 0) or 0)

    def get_clan_hashrate_bonus_multiplier(self, user_id: int) -> float:
        clan = self.get_clan_for_user(int(user_id))
        if not clan:
            return 1.0
        clan_id = int(clan.get("clan_id") or 0)
        if clan_id <= 0:
            return 1.0
        bonus_percent = self.get_clan_hashrate_bonus_percent(clan_id)
        return max(1.0, 1.0 + float(bonus_percent or 0))

    def get_hashrate_multiplier_for_user(self, user_id: int) -> float:
        return float(self.get_current_hashrate_multiplier()) * float(self.get_clan_hashrate_bonus_multiplier(int(user_id)))

    def clan_deposit_to_treasury(self, user_id: int, amount_usd: float) -> Tuple[bool, str, float]:
        amount = float(amount_usd or 0)
        if amount <= 0:
            return False, "❌ Сумма должна быть больше нуля.", 0.0

        clan = self.get_clan_for_user(int(user_id))
        if not clan:
            return False, "❌ Вы не состоите в клане.", 0.0

        clan_id = int(clan.get("clan_id") or 0)
        user = self.get_user(int(user_id))
        if not user:
            return False, "❌ Пользователь не найден.", 0.0

        balance = float(user.get("balance", 0) or 0)
        if balance < amount:
            return False, f"❌ Недостаточно средств. Доступно: {balance:.2f} USD", 0.0

        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, int(user_id)),
            )
            self.cursor.execute(
                "UPDATE clans SET treasury_usd = treasury_usd + ? WHERE clan_id = ?",
                (amount, clan_id),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, ?, NULL)",
                (clan_id, int(user_id), "treasury_deposit", amount),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось пополнить казну. Попробуйте позже.", 0.0

        self.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
        row = self.cursor.fetchone()
        new_treasury = float((row["treasury_usd"] if row else 0) or 0)
        return True, f"✅ Казна пополнена на {amount:.2f} USD", new_treasury

    def clan_withdraw_from_treasury(self, user_id: int, amount_usd: float) -> Tuple[bool, str, float]:
        amount = float(amount_usd or 0)
        if amount <= 0:
            return False, "❌ Сумма должна быть больше нуля.", 0.0

        clan = self.get_clan_for_user(int(user_id))
        if not clan:
            return False, "❌ Вы не состоите в клане.", 0.0

        if str(clan.get("member_role")) != "leader":
            return False, "❌ Выводить средства из казны может только глава клана.", 0.0

        clan_id = int(clan.get("clan_id") or 0)
        self.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
        row = self.cursor.fetchone()
        treasury = float((row["treasury_usd"] if row else 0) or 0)
        if treasury < amount:
            return False, f"❌ Недостаточно средств в казне. Доступно: {treasury:.2f} USD", treasury

        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "UPDATE clans SET treasury_usd = treasury_usd - ? WHERE clan_id = ?",
                (amount, clan_id),
            )
            self.cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, int(user_id)),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, ?, NULL)",
                (clan_id, int(user_id), "treasury_withdraw", amount),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось вывести средства из казны. Попробуйте позже.", treasury

        self.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
        row2 = self.cursor.fetchone()
        new_treasury = float((row2["treasury_usd"] if row2 else 0) or 0)
        return True, f"✅ Выведено из казны {amount:.2f} USD", new_treasury

    def clan_buy_hashrate_bonus(self, user_id: int, bonus_key: str, cost_usd: float, percent: float, duration_hours: int) -> Tuple[bool, str]:
        clan = self.get_clan_for_user(int(user_id))
        if not clan:
            return False, "❌ Вы не состоите в клане."

        if str(clan.get("member_role")) != "leader":
            return False, "❌ Покупать бонусы может только глава клана."

        clan_id = int(clan.get("clan_id") or 0)
        self.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
        row = self.cursor.fetchone()
        treasury = float((row["treasury_usd"] if row else 0) or 0)
        cost = float(cost_usd or 0)
        if cost <= 0:
            return False, "❌ Некорректная стоимость бонуса."
        if treasury < cost:
            return False, f"❌ Недостаточно средств в казне. Нужно: {cost:.2f} USD, доступно: {treasury:.2f} USD"

        expires_at = datetime.utcnow() + timedelta(hours=int(duration_hours))
        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "UPDATE clans SET treasury_usd = treasury_usd - ? WHERE clan_id = ?",
                (cost, clan_id),
            )
            self.cursor.execute(
                "INSERT INTO clan_active_bonuses (clan_id, bonus_key, percent, expires_at) VALUES (?, ?, ?, ?)",
                (clan_id, str(bonus_key), float(percent or 0), expires_at),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, ?, ?)",
                (clan_id, int(user_id), "bonus_purchase", cost, str(bonus_key)),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось купить бонус. Попробуйте позже."

        return True, "✅ Бонус куплен и применён ко всем участникам клана."

    def get_clan_members(self, clan_id: int) -> List[Dict]:
        self.cursor.execute(
            """
            SELECT m.user_id, m.role, m.joined_at, u.username
            FROM clan_members m
            LEFT JOIN users u ON u.user_id = m.user_id
            WHERE m.clan_id = ?
            ORDER BY CASE WHEN m.role = 'leader' THEN 0 ELSE 1 END, m.joined_at ASC
            """,
            (int(clan_id),),
        )
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    def leave_clan(self, user_id: int) -> Tuple[bool, str]:
        clan = self.get_clan_for_user(int(user_id))
        if not clan:
            return False, "❌ Вы не состоите в клане."

        if str(clan.get("member_role")) == "leader":
            return False, "❌ Глава клана не может выйти. Сначала передайте лидерство или распустите клан."

        clan_id = int(clan.get("clan_id") or 0)
        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?",
                (clan_id, int(user_id)),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, NULL, NULL)",
                (clan_id, int(user_id), "member_leave"),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось выйти из клана. Попробуйте позже."

        return True, "✅ Вы вышли из клана."

    def kick_clan_member(self, leader_id: int, target_user_id: int) -> Tuple[bool, str]:
        clan = self.get_clan_for_user(int(leader_id))
        if not clan:
            return False, "❌ Вы не состоите в клане."

        if str(clan.get("member_role")) != "leader":
            return False, "❌ Кикать участников может только глава клана."

        clan_id = int(clan.get("clan_id") or 0)
        if int(target_user_id) == int(leader_id):
            return False, "❌ Нельзя кикнуть самого себя."

        self.cursor.execute(
            "SELECT role FROM clan_members WHERE clan_id = ? AND user_id = ?",
            (clan_id, int(target_user_id)),
        )
        row = self.cursor.fetchone()
        if not row:
            return False, "❌ Этот игрок не состоит в вашем клане."
        if str(row["role"]) == "leader":
            return False, "❌ Нельзя кикнуть главу клана."

        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?",
                (clan_id, int(target_user_id)),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, NULL, ?)",
                (clan_id, int(leader_id), "member_kick", str(int(target_user_id))),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось кикнуть участника. Попробуйте позже."

        return True, "✅ Участник исключён из клана."

    def transfer_clan_leadership(self, leader_id: int, new_leader_id: int) -> Tuple[bool, str]:
        clan = self.get_clan_for_user(int(leader_id))
        if not clan:
            return False, "❌ Вы не состоите в клане."

        if str(clan.get("member_role")) != "leader":
            return False, "❌ Передать лидерство может только глава клана."

        clan_id = int(clan.get("clan_id") or 0)
        if int(new_leader_id) == int(leader_id):
            return False, "❌ Вы уже являетесь главой клана."

        self.cursor.execute(
            "SELECT role FROM clan_members WHERE clan_id = ? AND user_id = ?",
            (clan_id, int(new_leader_id)),
        )
        row = self.cursor.fetchone()
        if not row:
            return False, "❌ Этот игрок не состоит в вашем клане."
        if str(row["role"]) == "leader":
            return False, "❌ Этот игрок уже является главой клана."

        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "UPDATE clans SET leader_id = ? WHERE clan_id = ?",
                (int(new_leader_id), clan_id),
            )
            self.cursor.execute(
                "UPDATE clan_members SET role = 'member' WHERE clan_id = ? AND user_id = ?",
                (clan_id, int(leader_id)),
            )
            self.cursor.execute(
                "UPDATE clan_members SET role = 'leader' WHERE clan_id = ? AND user_id = ?",
                (clan_id, int(new_leader_id)),
            )
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, NULL, ?)",
                (clan_id, int(leader_id), "leader_transfer", f"{int(leader_id)}->{int(new_leader_id)}"),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось передать лидерство. Попробуйте позже."

        return True, "✅ Лидерство передано."

    def disband_clan(self, leader_id: int) -> Tuple[bool, str]:
        clan = self.get_clan_for_user(int(leader_id))
        if not clan:
            return False, "❌ Вы не состоите в клане."

        if str(clan.get("member_role")) != "leader":
            return False, "❌ Распустить клан может только глава клана."

        clan_id = int(clan.get("clan_id") or 0)
        try:
            self.cursor.execute("BEGIN")
            self.cursor.execute(
                "INSERT INTO clan_events (clan_id, actor_user_id, event_type, amount_usd, meta) VALUES (?, ?, ?, NULL, NULL)",
                (clan_id, int(leader_id), "clan_disband"),
            )
            self.cursor.execute(
                "DELETE FROM clans WHERE clan_id = ?",
                (clan_id,),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False, "❌ Не удалось распустить клан. Попробуйте позже."

        return True, "✅ Клан распущен."

    def get_user(self, user_id: int) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            return dict(row)
        return None

    def create_user(self, user_id: int, username: str = None):
        from models import get_starter_balance_usd
        from exchange_rate import get_bitcoin_exchange_rate

        rate = get_bitcoin_exchange_rate()
        starter_balance = int(get_starter_balance_usd(rate_usd_per_btc=rate) or 0)
        self.cursor.execute("""
            INSERT INTO users (user_id, username, balance, bitcoin_balance, last_collect_time, created_at, dust_level, dust_last_update)
            VALUES (?, ?, ?, 0, ?, ?, 0, ?)
        """, (user_id, username, starter_balance, datetime.now(), datetime.utcnow(), datetime.now()))
        self.conn.commit()

    def ensure_user_exists_for_admin_actions(self, user_id: int, username: str = None) -> None:
        existing = self.get_user(user_id)
        if existing:
            return

        now = datetime.now()
        self.cursor.execute(
            """
            INSERT OR IGNORE INTO users (
                user_id,
                username,
                balance,
                bitcoin_balance,
                bank_balance,
                bank_bitcoin_balance,
                total_hashrate,
                total_power_consumption,
                total_heat_generation,
                total_psu_power,
                total_cooling_efficiency,
                pending_bitcoin,
                mining_enabled,
                last_collect_time,
                dust_level,
                dust_last_update,
                is_banned,
                ban_reason
            )
            VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, 0, ?, 0, NULL)
            """,
            (user_id, username, now, now),
        )
        self.conn.commit()

                                    

    def get_dust_state(self, user_id: int) -> Tuple[float, Optional[datetime]]:
        user = self.get_user(user_id)
        if not user:
            return 0.0, None
        dust_level = float(user.get("dust_level", 0) or 0)
        last_update = user.get("dust_last_update")
        if isinstance(last_update, str):
            try:
                last_update = datetime.fromisoformat(last_update)
            except ValueError:
                last_update = None
        return dust_level, last_update

    def update_dust_state(self, user_id: int, dust_level: float, last_update: Optional[datetime] = None) -> None:
        if last_update is None:
            last_update = datetime.now()
        self.cursor.execute(
            """
            UPDATE users
            SET dust_level = ?, dust_last_update = ?
            WHERE user_id = ?
            """,
            (max(0.0, min(100.0, dust_level)), last_update, user_id),
        )
        self.conn.commit()

    def update_user_balance(self, user_id: int, amount: float):
        self.cursor.execute("""
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        """, (amount, user_id))
        self.conn.commit()

    def set_user_balance(self, user_id: int, amount: float):
        self.cursor.execute("""
            UPDATE users SET balance = ? WHERE user_id = ?
        """, (amount, user_id))
        self.conn.commit()

    def update_user_stats(self, user_id: int, stats: Dict):
        self.cursor.execute("""
            UPDATE users SET
                total_hashrate = ?,
                total_power_consumption = ?,
                total_heat_generation = ?,
                total_psu_power = ?,
                total_cooling_efficiency = ?,
                pending_bitcoin = ?,
                last_collect_time = ?
            WHERE user_id = ?
        """, (
            stats.get('hashrate', 0),
            stats.get('power_consumption', 0),
            stats.get('heat_generation', 0),
            stats.get('psu_power', 0),
            stats.get('cooling_efficiency', 0),
            stats.get('pending_bitcoin', 0),
            stats.get('last_collect_time', datetime.now()),
            user_id
        ))
        self.conn.commit()

    def reset_all_pending_bitcoin(self) -> int:
        now = datetime.now()
        self.cursor.execute(
            """
            UPDATE users
            SET pending_bitcoin = 0,
                last_collect_time = ?
            """,
            (now,),
        )
        self.conn.commit()
        rowcount = self.cursor.rowcount
        if rowcount is None or rowcount < 0:
            return 0
        return int(rowcount)
    
    def update_bitcoin_balance(self, user_id: int, amount: float):
        self.cursor.execute("""
            UPDATE users SET bitcoin_balance = bitcoin_balance + ? WHERE user_id = ?
        """, (amount, user_id))
        self.conn.commit()

                                            

    def move_all_balance_to_bank(self, user_id: int):
        user = self.get_user(user_id)
        if not user:
            return
        current_balance = user.get("balance", 0) or 0
        if current_balance <= 0:
            return
        self.cursor.execute(
            """
            UPDATE users
            SET balance = 0,
                bank_balance = bank_balance + ?
            WHERE user_id = ?
            """,
            (current_balance, user_id),
        )
        self.conn.commit()

    def withdraw_all_from_bank(self, user_id: int):
        user = self.get_user(user_id)
        if not user:
            return
        bank_balance = user.get("bank_balance", 0) or 0
        if bank_balance <= 0:
            return
        self.cursor.execute(
            """
            UPDATE users
            SET bank_balance = 0,
                balance = balance + ?
            WHERE user_id = ?
            """,
            (bank_balance, user_id),
        )
        self.conn.commit()

    def move_all_bitcoin_to_bank(self, user_id: int):
        user = self.get_user(user_id)
        if not user:
            return
        current_btc = user.get("bitcoin_balance", 0) or 0
        if current_btc <= 0:
            return
        self.cursor.execute(
            """
            UPDATE users
            SET bitcoin_balance = 0,
                bank_bitcoin_balance = bank_bitcoin_balance + ?
            WHERE user_id = ?
            """,
            (current_btc, user_id),
        )
        self.conn.commit()

    def withdraw_all_bitcoin_from_bank(self, user_id: int):
        user = self.get_user(user_id)
        if not user:
            return
        bank_btc = user.get("bank_bitcoin_balance", 0) or 0
        if bank_btc <= 0:
            return
        self.cursor.execute(
            """
            UPDATE users
            SET bank_bitcoin_balance = 0,
                bitcoin_balance = bitcoin_balance + ?
            WHERE user_id = ?
            """,
            (bank_btc, user_id),
        )
        self.conn.commit()

    def update_bank_balance(self, user_id: int, amount: float):
        self.cursor.execute(
            """
            UPDATE users
            SET bank_balance = bank_balance + ?
            WHERE user_id = ?
            """,
            (amount, user_id),
        )
        self.conn.commit()

    def update_bank_bitcoin_balance(self, user_id: int, amount: float):
        self.cursor.execute(
            """
            UPDATE users
            SET bank_bitcoin_balance = bank_bitcoin_balance + ?
            WHERE user_id = ?
            """,
            (amount, user_id),
        )
        self.conn.commit()

                                            

    def _generate_unique_address(self, prefix: str, column: str) -> str:
        if column not in {"usd_address", "btc_address"}:
            raise ValueError("Unsupported column")
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        while True:
                                                    
            raw = "".join(secrets.choice(alphabet) for _ in range(16))
            address = "-".join([raw[i:i+4] for i in range(0, 16, 4)])
            self.cursor.execute(f"SELECT 1 FROM users WHERE {column} = ?", (address,))
            if not self.cursor.fetchone():
                return address

    def ensure_user_wallet_addresses(self, user_id: int) -> Tuple[str, str]:
        user = self.get_user(user_id)
        if not user:
            return "", ""

        usd_address = user.get("usd_address") or ""
        btc_address = user.get("btc_address") or ""
        updated = False

                                                       
        if not usd_address and not btc_address:
            usd_address = self._generate_unique_address("ADDR", "usd_address")
            btc_address = usd_address
            updated = True
                                                                
        elif usd_address and not btc_address:
            btc_address = usd_address
            updated = True
        elif btc_address and not usd_address:
            usd_address = btc_address
            updated = True
                                                                           
        elif usd_address != btc_address:
            btc_address = usd_address
            updated = True

        if updated:
            self.cursor.execute(
                """
                UPDATE users
                SET usd_address = ?, btc_address = ?
                WHERE user_id = ?
                """,
                (usd_address, btc_address, user_id),
            )
            self.conn.commit()

        return usd_address, btc_address

    def get_user_by_usd_address(self, address: str) -> Optional[Dict]:
        self.cursor.execute(
            """
            SELECT * FROM users WHERE usd_address = ?
            """,
            (address,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_user_by_btc_address(self, address: str) -> Optional[Dict]:
        self.cursor.execute(
            """
            SELECT * FROM users WHERE btc_address = ?
            """,
            (address,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def is_wallet_address_taken(self, address: str, exclude_user_id: Optional[int] = None) -> bool:
        if not address:
            return False
        if exclude_user_id is not None:
            self.cursor.execute(
                """
                SELECT 1 FROM users
                WHERE (usd_address = ? OR btc_address = ?)
                  AND user_id != ?
                """,
                (address, address, exclude_user_id),
            )
        else:
            self.cursor.execute(
                """
                SELECT 1 FROM users
                WHERE usd_address = ? OR btc_address = ?
                """,
                (address, address),
            )
        return self.cursor.fetchone() is not None

    def set_user_wallet_address(self, user_id: int, address: str) -> bool:
        if not address:
            return False
        self.cursor.execute(
            """
            UPDATE users
            SET usd_address = ?, btc_address = ?
            WHERE user_id = ?
            """,
            (address, address, user_id),
        )
        self.conn.commit()
        return True
    
    def toggle_mining(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        
        current_state = user.get('mining_enabled', 0) or 0
        new_state = 1 if current_state == 0 else 0
        
        self.cursor.execute("""
            UPDATE users SET mining_enabled = ? WHERE user_id = ?
        """, (new_state, user_id))
        self.conn.commit()
        
        return new_state == 1

    def set_mining_enabled(self, user_id: int, enabled: bool) -> None:
        self.cursor.execute(
            """
            UPDATE users SET mining_enabled = ? WHERE user_id = ?
            """,
            (1 if enabled else 0, user_id),
        )
        self.conn.commit()
    
    def is_mining_enabled(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        return (user.get('mining_enabled', 0) or 0) == 1
    
    def get_installed_items(self, user_id: int) -> List[Dict]:
        self.cursor.execute("""
            SELECT * FROM installed_items WHERE user_id = ?
        """, (user_id,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def install_item(self, user_id: int, item_id: str, item_name: str, item_type: str, quantity: int = 1):
                                                      
        self.cursor.execute("""
            SELECT wear, is_broken FROM inventory 
            WHERE user_id = ? AND item_id = ? AND quantity >= ? AND is_broken = 0
            LIMIT 1
        """, (user_id, item_id, quantity))
        inv_item = self.cursor.fetchone()
        
        if not inv_item:
            return
        
        wear = inv_item['wear'] if inv_item['wear'] is not None else 100.0
        
                                          
        self.cursor.execute("""
            UPDATE inventory SET quantity = quantity - ?
            WHERE user_id = ? AND item_id = ? AND quantity >= ? AND is_broken = 0
        """, (quantity, user_id, item_id, quantity))
        
                                                    
        self.cursor.execute("""
            SELECT quantity FROM installed_items 
            WHERE user_id = ? AND item_id = ?
        """, (user_id, item_id))
        existing = self.cursor.fetchone()
        
        if existing:
                                                                            
            self.cursor.execute("""
                SELECT quantity, wear FROM installed_items 
                WHERE user_id = ? AND item_id = ?
            """, (user_id, item_id))
            current = self.cursor.fetchone()
            if current:
                current_qty = current['quantity']
                current_wear = current['wear'] if current['wear'] is not None else 100.0
                               
                avg_wear = ((current_wear * current_qty) + (wear * quantity)) / (current_qty + quantity)
                self.cursor.execute("""
                    UPDATE installed_items SET quantity = quantity + ?, wear = ?
                    WHERE user_id = ? AND item_id = ?
                """, (quantity, avg_wear, user_id, item_id))
        else:
                                                   
            self.cursor.execute("""
                INSERT INTO installed_items (user_id, item_id, item_name, item_type, quantity, wear)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, item_id, item_name, item_type, quantity, wear))
        
                                                             
        self.cursor.execute("""
            DELETE FROM inventory WHERE user_id = ? AND quantity <= 0
        """, (user_id,))
        
        self.conn.commit()
    
    def uninstall_item(self, user_id: int, item_id: str, quantity: int = 1):
                                                                  
        self.cursor.execute("""
            SELECT item_name, item_type, wear FROM installed_items 
            WHERE user_id = ? AND item_id = ? AND quantity >= ?
        """, (user_id, item_id, quantity))
        item = self.cursor.fetchone()
        
        if not item:
            return
        
        item_name = item['item_name']
        item_type = item['item_type']
        wear = item['wear'] if item['wear'] is not None else 100.0
        
                                            
        self.cursor.execute("""
            UPDATE installed_items SET quantity = quantity - ?
            WHERE user_id = ? AND item_id = ? AND quantity >= ?
        """, (quantity, user_id, item_id, quantity))
        
                                                  
        self.cursor.execute("""
            SELECT quantity, wear FROM inventory 
            WHERE user_id = ? AND item_id = ? AND is_broken = 0
        """, (user_id, item_id))
        existing = self.cursor.fetchone()
        
        if existing:
                           
            current_qty = existing['quantity']
            current_wear = existing['wear'] if existing['wear'] is not None else 100.0
            avg_wear = ((current_wear * current_qty) + (wear * quantity)) / (current_qty + quantity)
            self.cursor.execute("""
                UPDATE inventory SET quantity = quantity + ?, wear = ?
                WHERE user_id = ? AND item_id = ? AND is_broken = 0
            """, (quantity, avg_wear, user_id, item_id))
        else:
            self.cursor.execute("""
                INSERT INTO inventory (user_id, item_id, item_name, item_type, quantity, wear, is_broken)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (user_id, item_id, item_name, item_type, quantity, wear))
        
                                                                 
        self.cursor.execute("""
            DELETE FROM installed_items WHERE user_id = ? AND quantity <= 0
        """, (user_id,))
        
        self.conn.commit()

    def add_item_to_inventory(self, user_id: int, item_id: str, item_name: str, item_type: str, quantity: int = 1):
                                                                    
        self.cursor.execute("""
            SELECT quantity, wear FROM inventory 
            WHERE user_id = ? AND item_id = ? AND is_broken = 0
        """, (user_id, item_id))
        existing = self.cursor.fetchone()
        
        if existing:
                                                              
            current_qty = existing['quantity']
            current_wear = existing['wear'] if existing['wear'] is not None else 100.0
                                             
            avg_wear = ((current_wear * current_qty) + (100.0 * quantity)) / (current_qty + quantity)
            self.cursor.execute("""
                UPDATE inventory SET quantity = quantity + ?, wear = ?
                WHERE user_id = ? AND item_id = ? AND is_broken = 0
            """, (quantity, avg_wear, user_id, item_id))
        else:
                                                    
            unique_id = self._generate_unique_item_id()
            self.cursor.execute("""
                INSERT INTO inventory (user_id, item_id, item_name, item_type, quantity, wear, is_broken, unique_id)
                VALUES (?, ?, ?, ?, ?, 100.0, 0, ?)
            """, (user_id, item_id, item_name, item_type, quantity, unique_id))
        
        self.conn.commit()

    def _generate_unique_item_id(self) -> str:
        import secrets
        import string

        alphabet = string.ascii_uppercase + string.digits

        while True:
            raw = "".join(secrets.choice(alphabet) for _ in range(20))
            uid = "-".join(raw[i:i+4] for i in range(0, 20, 4))
                                                          
            self.cursor.execute("SELECT 1 FROM inventory WHERE unique_id = ? UNION SELECT 1 FROM installed_items WHERE unique_id = ?", (uid, uid))
            if not self.cursor.fetchone():
                return uid

    def get_user_inventory(self, user_id: int) -> List[Dict]:
        self.cursor.execute("""
            SELECT * FROM inventory WHERE user_id = ?
        """, (user_id,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def reset_user_account(self, user_id: int):
        from models import get_starter_balance_usd
        from exchange_rate import get_bitcoin_exchange_rate

                                                        
        self.cursor.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
        self.cursor.execute("DELETE FROM installed_items WHERE user_id = ?", (user_id,))
                                            
        self.cursor.execute("""
            UPDATE users SET 
                balance = ?,
                bitcoin_balance = 0,
                pending_bitcoin = 0,
                mining_enabled = 0,
                total_hashrate = 0,
                total_power_consumption = 0,
                total_heat_generation = 0,
                total_psu_power = 0,
                total_cooling_efficiency = 0,
                pending_bitcoin = 0,
                last_collect_time = ?,
                dust_level = 0,
                dust_last_update = ?
            WHERE user_id = ?

        """, (float(get_starter_balance_usd(rate_usd_per_btc=get_bitcoin_exchange_rate())), datetime.now(), datetime.now(), user_id))
        self.conn.commit()

    def get_top_players(self, limit: int = 10) -> List[Dict]:
        from exchange_rate import get_bitcoin_exchange_rate
        rate = get_bitcoin_exchange_rate()
        self.cursor.execute("""
            SELECT 
                user_id,
                username,
                balance,
                bitcoin_balance,
                (balance + bitcoin_balance * ?) as total_wealth
            FROM users
            WHERE balance > 0 OR bitcoin_balance > 0
            ORDER BY total_wealth DESC
            LIMIT ?
        """, (rate, limit))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_user_position(self, user_id: int) -> Optional[int]:
        from exchange_rate import get_bitcoin_exchange_rate
                                                                            
        user = self.get_user(user_id)
        if not user:
            return None
        
        user_balance = user.get('balance', 0) or 0
        user_btc = user.get('bitcoin_balance', 0) or 0
        rate = get_bitcoin_exchange_rate()
        user_wealth = user_balance + user_btc * rate
        
                                                              
        if user_wealth <= 0:
            return None
        
                                                         
        self.cursor.execute("""
            SELECT COUNT(*) as position
            FROM users
            WHERE (balance + bitcoin_balance * ?) > ?
            AND (balance > 0 OR bitcoin_balance > 0)
        """, (rate, user_wealth))
        row = self.cursor.fetchone()
        if row:
            return row['position'] + 1                                                       
        return None
    
    def get_top_players_by_hashrate(self, limit: int = 10) -> List[Dict]:
        self.cursor.execute("""
            SELECT 
                user_id,
                username,
                total_hashrate
            FROM users
            WHERE total_hashrate > 0
            ORDER BY total_hashrate DESC
            LIMIT ?
        """, (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_user_hashrate_position(self, user_id: int) -> Optional[int]:
        user = self.get_user(user_id)
        if not user:
            return None
        
        user_hashrate = user.get('total_hashrate', 0) or 0
        
                                                               
        if user_hashrate <= 0:
            return None
        
                                                        
        self.cursor.execute("""
            SELECT COUNT(*) as position
            FROM users
            WHERE total_hashrate > ?
            AND total_hashrate > 0
        """, (user_hashrate,))
        row = self.cursor.fetchone()
        if row:
            return row['position'] + 1                                                       
        return None
    
    def get_top_players_by_bitcoin(self, limit: int = 10) -> List[Dict]:
        self.cursor.execute("""
            SELECT 
                user_id,
                username,
                bitcoin_balance
            FROM users
            WHERE bitcoin_balance > 0
            ORDER BY bitcoin_balance DESC
            LIMIT ?
        """, (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_user_bitcoin_position(self, user_id: int) -> Optional[int]:
        user = self.get_user(user_id)
        if not user:
            return None
        
        user_btc = user.get('bitcoin_balance', 0) or 0
        
                                                                  
        if user_btc <= 0:
            return None
        
                                                           
        self.cursor.execute("""
            SELECT COUNT(*) as position
            FROM users
            WHERE bitcoin_balance > ?
            AND bitcoin_balance > 0
        """, (user_btc,))
        row = self.cursor.fetchone()
        if row:
            return row['position'] + 1                                                       
        return None
    
                                          
    
    def ban_user(self, user_id: int, reason: str = "Нарушение правил") -> bool:
        self.ensure_user_exists_for_admin_actions(user_id)
        
        self.cursor.execute("""
            UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?
        """, (reason, user_id))
        self.conn.commit()
        return True
    
    def unban_user(self, user_id: int) -> bool:
        self.ensure_user_exists_for_admin_actions(user_id)
        
        self.cursor.execute("""
            UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?
        """, (user_id,))
        self.conn.commit()
        return True
    
    def is_user_banned(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        return (user.get('is_banned', 0) or 0) == 1
    
    def get_ban_reason(self, user_id: int) -> Optional[str]:
        user = self.get_user(user_id)
        if not user:
            return None
        return user.get('ban_reason')
    
                                       
    
    def get_last_report_time(self, user_id: int) -> Optional[datetime]:
        user = self.get_user(user_id)
        if not user:
            return None
        last_report = user.get('last_report_time')
        if last_report:
            if isinstance(last_report, str):
                return datetime.fromisoformat(last_report)
            return last_report
        return None
    
    def update_last_report_time(self, user_id: int):
        self.cursor.execute("""
            UPDATE users SET last_report_time = ? WHERE user_id = ?
        """, (datetime.now(), user_id))
        self.conn.commit()

                            

    def add_chat_if_not_exists(
        self,
        chat_id: int,
        chat_type: str = "",
        title: str = "",
        username: str = "",
        invite_link: str = "",
    ):
        self.cursor.execute("""
            INSERT OR IGNORE INTO chats (chat_id, chat_type, title, username, invite_link)
            VALUES (?, ?, ?, ?, ?)
        """, (chat_id, chat_type, title, username, invite_link))
        self.cursor.execute("""
            UPDATE chats
            SET chat_type = ?,
                title = ?,
                username = COALESCE(NULLIF(?, ''), username),
                invite_link = COALESCE(NULLIF(?, ''), invite_link),
                updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
        """, (chat_type, title, username, invite_link, chat_id))
        self.conn.commit()

    def get_all_chats(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM chats")
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

                                        

    def get_all_users(self) -> List[Dict]:
        self.cursor.execute(
            """
            SELECT
                user_id,
                username,
                balance,
                bitcoin_balance,
                bank_balance,
                bank_bitcoin_balance
            FROM users
            """
        )
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

                                  

    def get_stats(self) -> Dict:
                                  
        self.cursor.execute("SELECT COUNT(*) as count FROM users")
        users_count = self.cursor.fetchone()['count']

                          
        self.cursor.execute("SELECT COUNT(*) as count FROM chats")
        chats_count = self.cursor.fetchone()['count']

                                    
        self.cursor.execute("SELECT COUNT(*) as count FROM chats WHERE chat_type IN ('group', 'supergroup')")
        groups_count = self.cursor.fetchone()['count']

                                    
        self.cursor.execute("SELECT COUNT(*) as count FROM chats WHERE chat_type = 'private'")
        private_count = self.cursor.fetchone()['count']

                                               
        self.cursor.execute("SELECT COUNT(*) as count FROM users WHERE mining_enabled = 1")
        active_miners = self.cursor.fetchone()['count']

                                      
        self.cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = 1")
        banned_count = self.cursor.fetchone()['count']

                                                         
        self.cursor.execute("SELECT COALESCE(SUM(balance), 0) + COALESCE(SUM(bank_balance), 0) as total FROM users")
        total_usd = self.cursor.fetchone()['total'] or 0

                                                         
        self.cursor.execute("SELECT COALESCE(SUM(bitcoin_balance), 0) + COALESCE(SUM(bank_bitcoin_balance), 0) as total FROM users")
        total_btc = self.cursor.fetchone()['total'] or 0

                                           
        self.cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total FROM inventory")
        inventory_items = self.cursor.fetchone()['total'] or 0

                                                
        self.cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total FROM installed_items")
        installed_items = self.cursor.fetchone()['total'] or 0

        return {
            'users_count': users_count,
            'chats_count': chats_count,
            'groups_count': groups_count,
            'private_count': private_count,
            'active_miners': active_miners,
            'banned_count': banned_count,
            'total_usd': total_usd,
            'total_btc': total_btc,
            'inventory_items': inventory_items,
            'installed_items': installed_items,
        }
    
    def repair_equipment(self, user_id: int, item_id: str, quantity: int = 1) -> Tuple[bool, float]:
                                                   
        self.cursor.execute("""
            SELECT quantity, wear FROM inventory 
            WHERE user_id = ? AND item_id = ? AND is_broken = 0 AND quantity >= ?
        """, (user_id, item_id, quantity))
        item = self.cursor.fetchone()
        
        if not item:
            return False, 0.0
        
        from models import get_item_price_usd

        price_usd = float(get_item_price_usd(item_id) or 0)
        if price_usd <= 0:
            return False, 0.0

                                                             
        repair_cost_per_unit = price_usd * 0.10
        total_cost = repair_cost_per_unit * quantity
        
                                       
        self.cursor.execute("""
            UPDATE inventory SET wear = 100.0
            WHERE user_id = ? AND item_id = ? AND is_broken = 0 AND quantity >= ?
        """, (user_id, item_id, quantity))
        
        self.conn.commit()
        return True, total_cost
    
    def scrap_equipment(self, user_id: int, item_id: str, quantity: int = 1) -> Tuple[bool, float]:
                                                   
        self.cursor.execute("""
            SELECT quantity FROM inventory 
            WHERE user_id = ? AND item_id = ? AND is_broken = 1 AND quantity >= ?
        """, (user_id, item_id, quantity))
        item = self.cursor.fetchone()
        
        if not item:
            return False, 0.0

        from models import get_item_price_usd

        price_usd = float(get_item_price_usd(item_id) or 0)
        if price_usd <= 0:
            return False, 0.0

                                                               
        scrap_value_per_unit = price_usd * 0.05
        total_value = scrap_value_per_unit * quantity
        
                              
        self.cursor.execute("""
            UPDATE inventory SET quantity = quantity - ?
            WHERE user_id = ? AND item_id = ? AND is_broken = 1 AND quantity >= ?
        """, (quantity, user_id, item_id, quantity))
        
        self.cursor.execute("""
            DELETE FROM inventory WHERE user_id = ? AND quantity <= 0
        """, (user_id,))
        
        self.conn.commit()
        return True, total_value

                                                                         
    
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        self.cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        if row:
            return row["value"]
        return default
    
    def set_setting(self, key: str, value: str) -> None:
        self.cursor.execute("""
            INSERT OR REPLACE INTO bot_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        self.conn.commit()
    
    def is_x2_mode_enabled(self) -> bool:
        return self.get_setting("x2_mode", "0") == "1"
    
    def set_x2_mode(self, enabled: bool) -> None:
        self.set_setting("x2_mode", "1" if enabled else "0")
    
    def is_x2_weekend_mode_enabled(self) -> bool:
        return self.get_setting("x2_weekend_mode", "0") == "1"
    
    def set_x2_weekend_mode(self, enabled: bool) -> None:
        self.set_setting("x2_weekend_mode", "1" if enabled else "0")
    
    def is_x2_newyear_mode_enabled(self) -> bool:
        return self.get_setting("x2_newyear_mode", "0") == "1"
    
    def set_x2_newyear_mode(self, enabled: bool) -> None:
        self.set_setting("x2_newyear_mode", "1" if enabled else "0")
    
    def get_current_hashrate_multiplier(self) -> float:
                             
        if self.is_x2_mode_enabled():
            return 2.0
        
                             
        if self.is_x2_newyear_mode_enabled():
            return 2.0
        
                                                        
        if self.is_x2_weekend_mode_enabled():
            from datetime import datetime
            weekday = datetime.now().weekday()
            if weekday in (5, 6):                           
                return 2.0
        
        return 1.0


                                  
db = Database()