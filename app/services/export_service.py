# -*- coding: utf-8 -*-
"""Сервис экспорта: CSV / Excel / формат для GLPI."""
import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.models.database import get_db, ASSET_TYPES

# Колонки обычного экспорта
EXPORT_COLUMNS = [
    ("name", "Имя"), ("type", "Тип"), ("status", "Статус"), ("location", "Местоположение"),
    ("user_fio", "Пользователь"), ("serial", "Серийный номер"),
    ("manufacturer", "Производитель"), ("model", "Модель"),
    ("inventory_no", "Инвентарный номер"), ("ip", "IP"), ("mac", "MAC"),
    ("notes", "Примечания"), ("updated_at", "Обновлено"),
]

# Формат GLPI (компьютеры): колонки согласно типовому импорту GLPI Computer
GLPI_COLUMNS = [
    ("Name", "name"), ("Comment", "notes"), ("Serial", "serial"),
    ("OtherSerial", ""), ("UUID", ""), ("Locations", "location"),
    ("Manufacturers", "manufacturer"), ("Models", "model"),
    ("NumInventory", "inventory_no"), ("Ip", "ip"), ("NameUser", "user_fio"),
    ("OperatingSystem", "os_version"), ("Domain", ""),
]


class ExportService:
    def __init__(self) -> None:
        self.db = get_db()

    def _rows(self, atype: str | None) -> list[dict]:
        return self.db.get_assets(atype=atype)

    # ---------- CSV ----------
    def export_csv(self, path: str | Path, atype: str | None = None) -> int:
        rows = self._rows(atype)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", newline="", encoding="utf-8-sig") as f:  # BOM для Excel
            w = csv.writer(f, delimiter=";")
            w.writerow([label for _, label in EXPORT_COLUMNS])
            for r in rows:
                w.writerow([r.get(key, "") or "" for key, _ in EXPORT_COLUMNS])
        self.db.log_event("export_csv", None, {"file": str(p), "count": len(rows)})
        return len(rows)

    # ---------- Excel ----------
    def export_excel(self, path: str | Path, atype: str | None = None) -> int:
        rows = self._rows(atype)
        data = [{label: r.get(key, "") or "" for key, label in EXPORT_COLUMNS} for r in rows]
        df = pd.DataFrame(data, columns=[label for _, label in EXPORT_COLUMNS])
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(p, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Активы", index=False)
            ws = writer.sheets["Активы"]
            for col_cells in ws.columns:  # автоширина колонок
                width = max(len(str(c.value)) if c.value else 0 for c in col_cells)
                letter = col_cells[0].column_letter
                ws.column_dimensions[letter].width = min(max(width + 2, 10), 45)
        self.db.log_event("export_excel", None, {"file": str(p), "count": len(rows)})
        return len(rows)

    # ---------- GLPI ----------
    def export_glpi(self, path: str | Path, atype: str = "computer") -> int:
        """Экспорт компьютеров в CSV-формате импорта GLPI (Computer)."""
        rows = self._rows(atype)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow([glpi_name for glpi_name, _ in GLPI_COLUMNS])
            for r in rows:
                hw = self.db.get_hardware(int(r["id"])) or {}
                line = []
                for _, key in GLPI_COLUMNS:
                    if key == "os_version":
                        line.append(hw.get("os_version", ""))
                    elif key == "Domain":
                        line.append("")
                    else:
                        line.append(r.get(key, "") or "")
                w.writerow(line)
        self.db.log_event("export_glpi", None, {"file": str(p), "count": len(rows)})
        return len(rows)

    @staticmethod
    def suggest_filename(ext: str, atype: str | None = None) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        part = ASSET_TYPES.get(atype or "", "Все активы").replace(" ", "_")
        return f"AscoldIT_{part}_{stamp}.{ext}"
