# -*- coding: utf-8 -*-
"""Модуль конфигурации AscoldIT.

При первом запуске создаёт папку %APPDATA%\\AscoldIT\\ (или ~/.config/AscoldIT
на других ОС) с файлами config.json и assets.db.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "AscoldIT"
APP_VERSION = "1.0.0 (M1)"

# Значения конфигурации по умолчанию
DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "auto",                # auto | light | dark
    "accent_color": "#0078d4",      # цвет акцента Windows 11
    "db_path": "",                  # пустая строка => assets.db в папке конфига
    "ad": {
        "enabled": False,
        "server": "",               # например dc01.corp.local
        "domain": "",               # corp.local
        "base_dn": "",              # DC=corp,DC=local
        "username": "",             # пусто => текущий пользователь (Kerberos)
        "password": "",             # хранится в XOR-obfuscated виде (не секрет)
        "use_current_user": True,
    },
    "last_import_mapping": {},      # последние маппинги импорта: {источник: поле}
    "last_export_dir": "",
}


def config_dir() -> Path:
    """Каталог конфигурации приложения (%APPDATA%\\AscoldIT на Windows)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_file() -> Path:
    return config_dir() / "config.json"


def default_db_path() -> Path:
    """Путь к БД по умолчанию: %APPDATA%\\AscoldIT\\assets.db."""
    return config_dir() / "assets.db"


class Config:
    """Лёгкий JSON-конфиг с поддержкой вложенных ключей через точку."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
        self.load()

    # ---------- загрузка/сохранение ----------
    def load(self) -> None:
        f = config_file()
        if f.exists():
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                self._merge(self._data, loaded)
            except Exception:
                # повреждённый конфиг — оставляем значения по умолчанию
                pass
        else:
            self.save()

    def save(self) -> None:
        with open(config_file(), "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    @staticmethod
    def _merge(dst: dict, src: dict) -> None:
        """Рекурсивное слияние src в dst (значения из файла приоритетны)."""
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                Config._merge(dst[k], v)
            else:
                dst[k] = v

    # ---------- доступ ----------
    def get(self, key: str, default: Any = None) -> Any:
        """Доступ по точечному ключу, напр. get('ad.server')."""
        cur: Any = self._data
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        cur = self._data
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value

    @property
    def db_path(self) -> Path:
        raw = self.get("db_path") or ""
        return Path(raw) if raw else default_db_path()

    @db_path.setter
    def db_path(self, value: str | Path) -> None:
        self.set("db_path", str(value))


# Глобальный синглтон конфига
config = Config()
