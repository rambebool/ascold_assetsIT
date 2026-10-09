# -*- coding: utf-8 -*-
"""Модель данных AscoldIT: SQLite-хранилище (assets, hardware, users, locations, events)."""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.utils.config import config

# Схема базы данных
SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT NOT NULL CHECK (type IN ('computer','mfp','printer','phone','peripheral','netdev')),
    name         TEXT NOT NULL,
    status       TEXT DEFAULT 'Эксплуатируется',
    location     TEXT DEFAULT '',
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    serial       TEXT DEFAULT '',
    manufacturer TEXT DEFAULT '',
    model        TEXT DEFAULT '',
    inventory_no TEXT DEFAULT '',
    ip           TEXT DEFAULT '',
    mac          TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_type   ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_name   ON assets(name);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);

CREATE TABLE IF NOT EXISTS hardware (
    asset_id    INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    cpu         TEXT DEFAULT '',
    ram_total   TEXT DEFAULT '',
    ram_type    TEXT DEFAULT '',
    disk_type   TEXT DEFAULT '',
    disk_size   TEXT DEFAULT '',
    gpu         TEXT DEFAULT '',
    os_version  TEXT DEFAULT '',
    bios_serial TEXT DEFAULT '',
    last_seen   TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fio        TEXT NOT NULL,
    department TEXT DEFAULT '',
    ad_login   TEXT DEFAULT '',
    phone      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS locations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    name      TEXT NOT NULL,
    type      TEXT NOT NULL CHECK (type IN ('building','floor','dept','room'))
);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    user         TEXT NOT NULL,
    action       TEXT NOT NULL,
    asset_id     INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    details_json TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_asset ON events(asset_id);
"""

# Разрешённые типы активов и человекочитаемые названия
ASSET_TYPES = {
    "computer": "Компьютер",
    "mfp": "Сетевой МФУ",
    "printer": "Принтер",
    "phone": "Телефон",
    "peripheral": "Периферия",
    "netdev": "Сетевое устройство",
}

ASSET_STATUSES = [
    "Эксплуатируется",
    "В резерве",
    "На ремонте",
    "Списан",
    "Не проверено",
]


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def current_user() -> str:
    """Текущий пользователь ОС (для журнала событий)."""
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return "unknown"


class Database:
    """Потокобезопасная обёртка над sqlite3. Одно соединение на поток."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else config.db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------- низкоуровневые операции ----------
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ---------- активы ----------
    def add_asset(self, data: dict) -> int:
        ts = now_iso()
        cur = self.execute(
            """INSERT INTO assets
               (type, name, status, location, user_id, serial, manufacturer,
                model, inventory_no, ip, mac, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("type", "computer"), data.get("name", ""),
                data.get("status", "Эксплуатируется"), data.get("location", ""),
                data.get("user_id"), data.get("serial", ""),
                data.get("manufacturer", ""), data.get("model", ""),
                data.get("inventory_no", ""), data.get("ip", ""),
                data.get("mac", ""), data.get("notes", ""), ts, ts,
            ),
        )
        asset_id = int(cur.lastrowid)
        self.log_event("create", asset_id, {"type": data.get("type"), "name": data.get("name")})
        return asset_id

    def update_asset(self, asset_id: int, data: dict) -> None:
        fields = ["type", "name", "status", "location", "user_id", "serial",
                  "manufacturer", "model", "inventory_no", "ip", "mac", "notes"]
        sets = ", ".join(f"{f} = ?" for f in fields if f in data)
        vals = [data[f] for f in fields if f in data]
        if sets:
            vals.append(now_iso())
            self.execute(f"UPDATE assets SET {sets}, updated_at = ? WHERE id = ?", tuple(vals))
            self.log_event("update", asset_id, {k: v for k, v in data.items() if k in fields})

    def delete_asset(self, asset_id: int) -> None:
        row = self.get_asset(asset_id)
        self.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        if row:
            self.log_event("delete", None, {"asset": row["name"], "asset_id": asset_id})

    def get_asset(self, asset_id: int) -> Optional[dict]:
        return self.query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))

    def get_assets(self, atype: Optional[str] = None, search: str = "",
                   status: str = "") -> list[dict]:
        sql = (
            "SELECT a.*, u.fio AS user_fio FROM assets a "
            "LEFT JOIN users u ON u.id = a.user_id WHERE 1=1"
        )
        params: list[Any] = []
        if atype:
            sql += " AND a.type = ?"
            params.append(atype)
        if status:
            sql += " AND a.status = ?"
            params.append(status)
        if search:
            like = f"%{search.lower()}%"
            sql += (" AND (lower(a.name) LIKE ? OR lower(a.ip) LIKE ? OR lower(a.mac) LIKE ?"
                    " OR lower(a.location) LIKE ? OR lower(a.model) LIKE ? OR lower(u.fio) LIKE ?)")
            params += [like] * 6
        sql += " ORDER BY a.name COLLATE NOCASE"
        return self.query(sql, tuple(params))

    # ---------- железо ----------
    def get_hardware(self, asset_id: int) -> Optional[dict]:
        return self.query_one("SELECT * FROM hardware WHERE asset_id = ?", (asset_id,))

    def upsert_hardware(self, asset_id: int, data: dict) -> None:
        cols = ["cpu", "ram_total", "ram_type", "disk_type", "disk_size",
                "gpu", "os_version", "bios_serial", "last_seen"]
        existing = self.get_hardware(asset_id)
        values = {c: data.get(c, (existing or {}).get(c, "")) for c in cols}
        if not values.get("last_seen"):
            values["last_seen"] = now_iso()
        if existing:
            self.execute(
                "UPDATE hardware SET cpu=?, ram_total=?, ram_type=?, disk_type=?,"
                " disk_size=?, gpu=?, os_version=?, bios_serial=?, last_seen=? WHERE asset_id=?",
                (*[values[c] for c in cols], asset_id),
            )
        else:
            self.execute(
                "INSERT INTO hardware (asset_id, cpu, ram_total, ram_type, disk_type,"
                " disk_size, gpu, os_version, bios_serial, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (asset_id, *[values[c] for c in cols]),
            )
        self.log_event("hardware_update", asset_id, values)

    # ---------- пользователи ----------
    def get_users(self) -> list[dict]:
        return self.query("SELECT * FROM users ORDER BY fio COLLATE NOCASE")

    def upsert_user_by_login(self, fio: str, ad_login: str, department: str = "") -> int:
        row = self.query_one("SELECT id FROM users WHERE ad_login = ?", (ad_login.lower(),))
        if row:
            self.execute("UPDATE users SET fio=?, department=? WHERE id=?", (fio, department, row["id"]))
            return int(row["id"])
        cur = self.execute("INSERT INTO users (fio, department, ad_login, phone) VALUES (?,?,?,?)",
                           (fio, department, ad_login.lower(), ""))
        return int(cur.lastrowid)

    # ---------- локации ----------
    def get_locations(self) -> list[dict]:
        return self.query("SELECT * FROM locations ORDER BY name")

    # ---------- события ----------
    def log_event(self, action: str, asset_id: Optional[int], details: dict) -> None:
        self.execute(
            "INSERT INTO events (ts, user, action, asset_id, details_json) VALUES (?,?,?,?,?)",
            (now_iso(), current_user(), action, asset_id,
             json.dumps(details, ensure_ascii=False, default=str)),
        )

    def get_events(self, asset_id: Optional[int] = None, limit: int = 200) -> list[dict]:
        if asset_id is not None:
            rows = self.query(
                "SELECT * FROM events WHERE asset_id = ? ORDER BY ts DESC LIMIT ?",
                (asset_id, limit),
            )
        else:
            rows = self.query("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))
        for r in rows:
            try:
                r["details"] = json.loads(r.get("details_json") or "{}")
            except Exception:
                r["details"] = {}
        return rows


# Глобальный синглтон БД (ленивая инициализация)
_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def reinit_db(path: Optional[Path] = None) -> Database:
    """Пересоздать соединение с БД (при смене пути в настройках)."""
    global _db
    if _db is not None:
        try:
            _db.close()
        except Exception:
            pass
    _db = Database(path)
    return _db
