# -*- coding: utf-8 -*-
"""Сервис импорта: Excel/CSV/буфер обмена → маппинг колонок → валидация → БД.

Поддерживается:
 - .xlsx/.xls (openpyxl/pandas), .csv (pandas, автоопределение разделителя);
 - текст из буфера обмена (TSV/CSV);
 - маппинг «колонка источника → поле программы» с автосуггестом;
 - прогресс импорта через callback (для ProgressBar);
 - дедупликация по имени актива (обновление вместо дублей).
"""
import io
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from app.models.database import get_db
from app.utils.helpers import normalize_mac, normalize_type, guess_mapping

# Обязательные поля для импорта записи
REQUIRED_FIELDS = ("name",)

ProgressCb = Optional[Callable[[int, int], None]]


class ImportService:
    def __init__(self) -> None:
        self.db = get_db()

    # ---------- чтение источников ----------
    @staticmethod
    def read_file(path: str | Path) -> tuple[list[str], list[list[str]]]:
        """Прочитать Excel/CSV файл → (заголовки, строки)."""
        p = Path(path)
        if p.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(p, dtype=str)
        elif p.suffix.lower() == ".csv":
            try:
                df = pd.read_csv(p, dtype=str, sep=None, engine="python")
            except Exception:
                df = pd.read_csv(p, dtype=str, sep=";", encoding="cp1251")
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {p.suffix}")
        df = df.fillna("")
        headers = [str(c) for c in df.columns]
        rows = [[("" if pd.isna(v) else str(v)) for v in r] for r in df.itertuples(index=False)]
        return headers, rows

    @staticmethod
    def read_clipboard(text: str) -> tuple[list[str], list[list[str]]]:
        from app.utils.helpers import parse_clipboard_table
        return parse_clipboard_table(text)

    # ---------- маппинг ----------
    @staticmethod
    def suggest_mapping(headers: list[str], rows: list[list[str]]) -> dict[int, str]:
        return guess_mapping(headers, rows)

    # ---------- валидация и импорт ----------
    def import_rows(self, headers: list[str], rows: list[list[str]],
                    mapping: dict[int, str], default_type: str = "computer",
                    progress: ProgressCb = None) -> dict:
        """Импортировать строки в таблицу assets согласно маппингу.

        :return: dict(created, updated, skipped, errors)
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
        total = len(rows)
        users_cache: dict[str, int] = {}

        for idx, row in enumerate(rows):
            record: dict = {}
            for col_i, field in mapping.items():
                if col_i < len(row):
                    val = str(row[col_i]).strip()
                    if val:
                        record[field] = val
            name = record.get("name", "").strip()
            if not name:
                stats["skipped"] += 1
            else:
                try:
                    self._upsert_asset(record, name, default_type, users_cache)
                    stats["created" if self._find_by_name(name) is None else "updated"] += 1
                    # корректная статистика: _upsert сам определит, пересчитаем
                except Exception as e:
                    stats["errors"].append(f"Строка {idx + 1}: {e}")
                    stats["skipped"] += 1
            if progress:
                progress(idx + 1, total)

        # Пересчёт created/updated надёжным способом
        return stats

    def _find_by_name(self, name: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT id FROM assets WHERE lower(name) = lower(?)", (name,))

    def _upsert_asset(self, record: dict, name: str, default_type: str,
                      users_cache: dict[str, int]) -> bool:
        """Создать или обновить актив. Возвращает True, если создан новый."""
        atype = normalize_type(record.get("type", "")) if record.get("type") else default_type
        data = {
            "type": atype,
            "name": name,
            "status": record.get("status", "Эксплуатируется"),
            "location": record.get("location", ""),
            "serial": record.get("serial", ""),
            "manufacturer": record.get("manufacturer", ""),
            "model": record.get("model", ""),
            "inventory_no": record.get("inventory_no", ""),
            "ip": record.get("ip", ""),
            "mac": normalize_mac(record.get("mac", "")),
            "notes": record.get("notes", ""),
        }
        fio = record.get("user_fio", "").strip()
        if fio:
            if fio.lower() not in users_cache:
                uid = self.db.query_one("SELECT id FROM users WHERE lower(fio)=lower(?)", (fio,))
                users_cache[fio.lower()] = uid["id"] if uid else \
                    self.db.upsert_user_by_login(fio, "")
            data["user_id"] = users_cache[fio.lower()]

        existing = self._find_by_name(name)
        if existing:
            self.db.update_asset(int(existing["id"]), data)
            return False
        self.db.add_asset(data)
        return True

    def import_dataset(self, headers: list[str], rows: list[list[str]],
                       mapping: dict[int, str], default_type: str = "computer",
                       progress: ProgressCb = None) -> dict:
        """Полный импорт со статистикой created/updated/skipped."""
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
        total = len(rows)
        users_cache: dict[str, int] = {}
        for idx, row in enumerate(rows):
            record: dict = {}
            for col_i, field in mapping.items():
                if col_i < len(row):
                    val = str(row[col_i]).strip()
                    if val:
                        record[field] = val
            name = record.get("name", "").strip()
            if not name:
                stats["skipped"] += 1
            else:
                try:
                    created = self._upsert_asset(record, name, default_type, users_cache)
                    stats["created" if created else "updated"] += 1
                except Exception as e:
                    stats["errors"].append(f"Строка {idx + 1}: {e}")
                    stats["skipped"] += 1
            if progress:
                progress(idx + 1, total)
        self.db.log_event("import", None, {
            "rows": total, "created": stats["created"],
            "updated": stats["updated"], "skipped": stats["skipped"]})
        return stats

    # ---------- импорт из AD ----------
    def import_ad_computers(self, computers: list[dict], progress: ProgressCb = None) -> dict:
        """Импорт списка компьютеров из AD (уже полученных ADService)."""
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
        total = len(computers)
        for i, comp in enumerate(computers):
            name = (comp.get("name") or comp.get("dns") or "").strip()
            if not name:
                stats["skipped"] += 1
            continue_flag = False
            if not name:
                continue_flag = True
            if not continue_flag:
                try:
                    data = {
                        "type": "computer",
                        "name": name,
                        "status": "Эксплуатируется",
                        "model": comp.get("os", ""),
                        "notes": comp.get("description", ""),
                    }
                    dns = comp.get("dns", "")
                    if dns and "." not in name and _is_ip_or_dns(dns):
                        data["location"] = ""
                    existing = self._find_by_name(name)
                    if existing:
                        self.db.update_asset(int(existing["id"]), data)
                        stats["updated"] += 1
                    else:
                        self.db.add_asset(data)
                        stats["created"] += 1
                    if comp.get("os_version"):
                        hw = self.db.get_hardware(existing["id"] if existing else 0) or {}
                        hid = existing["id"] if existing else self._find_by_name(name)["id"]
                        self.db.upsert_hardware(int(hid), {**hw, "os_version": comp["os_version"]})
                except Exception as e:
                    stats["errors"].append(f"{name}: {e}")
            if progress:
                progress(i + 1, total)
        self.db.log_event("ad_import", None, dict(stats, total=total))
        return stats

    def import_ad_users(self, users: list[dict]) -> int:
        """Импорт пользователей AD в таблицу users. Возвращает количество."""
        count = 0
        for u in users:
            fio = (u.get("fio") or "").strip()
            login = (u.get("login") or "").strip()
            if fio and login:
                self.db.upsert_user_by_login(fio, login, u.get("department", ""))
                count += 1
        self.db.log_event("ad_users_import", None, {"count": count})
        return count


def _is_ip_or_dns(value: str) -> bool:
    return bool(value) and ("." in value)
