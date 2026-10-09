# -*- coding: utf-8 -*-
"""Вспомогательные функции: умное распознавание типов полей и нормализация данных."""
import re
from typing import Optional

# Поля программы, в которые можно маппить колонки импорта
FIELD_LABELS: dict[str, str] = {
    "name": "Имя актива",
    "type": "Тип устройства",
    "status": "Статус",
    "location": "Местоположение",
    "serial": "Серийный номер",
    "manufacturer": "Производитель",
    "model": "Модель",
    "inventory_no": "Инвентарный номер",
    "ip": "IP-адрес",
    "mac": "MAC-адрес",
    "user_fio": "Пользователь (ФИО)",
    "notes": "Примечания",
}

_IP_RE = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$")
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$|^([0-9A-Fa-f]{12})$")
_FIO_RE = re.compile(r"^[А-ЯЁA-Z][а-яёa-z]*[\s\-]+[А-ЯЁA-Z][а-яёa-z]*(\s+[А-ЯЁA-Z][а-яёa-z]*)?")
_INVENTORY_RE = re.compile(r"^[\w\-/]{6,20}$")
_DEVICE_NAME_RE = re.compile(r"^(PC|WKST|NB|LAPTOP|srv|server|ws|nb)[-_\d]", re.IGNORECASE)

# Соответствие русских названий типов устройств внутренним кодам
TYPE_ALIASES: dict[str, str] = {
    "компьютер": "computer", "пк": "computer", "pc": "computer", "computer": "computer",
    "ноутбук": "computer", "notebook": "computer", "laptop": "computer",
    "мфу": "mfp", "mfp": "mfp", "смартфун": "mfp", "узо": "mfp",
    "принтер": "printer", "printer": "printer",
    "телефон": "phone", "phone": "phone", "телефония": "phone",
    "периферия": "peripheral", "peripheral": "peripheral", "монитор": "peripheral",
    "сеть": "netdev", "netdev": "netdev", "коммутатор": "netdev", "switch": "netdev",
    "маршрутизатор": "netdev", "router": "netdev", "точка доступа": "netdev", "ap": "netdev",
}


def detect_field_type(value: str) -> Optional[str]:
    """Умное распознавание типа поля по значению.

    Возвращает один из: ip, mac, fio, location, device_name, inventory,
    manufacturer, status или None.
    """
    v = (value or "").strip()
    if not v:
        return None
    if _IP_RE.match(v):
        return "ip"
    if _MAC_RE.match(v):
        return "mac"
    if _FIO_RE.match(v) and len(v.split()) >= 2 and any(c.isupper() for c in v):
        # ФИО: Иванов Иван Иванович / Иванов И.И.
        return "fio"
    low = v.lower()
    if low in TYPE_ALIASES:
        return "type"
    if low in ("эксплуатируется", "в резерве", "на ремонте", "списан", "не проверено",
               "активен", "исправен", "износ"):
        return "status"
    if _INVENTORY_RE.match(v) and any(c.isdigit() for c in v) and not v.isalpha():
        return "inventory"
    if _DEVICE_NAME_RE.match(v) and any(c.isdigit() for c in v):
        return "device_name"
    if re.search(r"(кабинет|комната|этаж|здание|корпус|\b\d{2,4}\b\s*[-–]?\s*\d*)", low):
        return "location"
    if len(v) <= 30 and v.isalpha() and v[0].isupper():
        return "manufacturer"
    return None


def guess_mapping(headers: list[str], sample_rows: list[list[str]]) -> dict[int, str]:
    """Предложить маппинг «номер колонки → поле программы» по заголовкам и данным.

    Использует эвристику по названиям колонок и распознавание значений.
    """
    mapping: dict[int, str] = {}
    header_keywords = [
        (("имя", "hostname", "name", "название", "компьютер"), "name"),
        (("ip", "адрес ип", "ип"), "ip"),
        (("mac",), "mac"),
        (("фио", "fio", "пользовател", "владел", "employee", "user"), "user_fio"),
        (("местоположен", "кабинет", "расположен", "location", "office", "адрес"), "location"),
        (("статус", "status", "состояни"), "status"),
        (("серий", "serial", "s/n", "sn"), "serial"),
        (("производител", "manufacturer", "vendor", "бренд"), "manufacturer"),
        (("модель", "model"), "model"),
        (("инвентар", "inventory", "инв"), "inventory_no"),
        (("тип", "type", "категори"), "type"),
        (("примечан", "note", "comment", "описан"), "notes"),
    ]
    used_fields: set[str] = set()
    for i, h in enumerate(headers):
        hl = (h or "").lower().strip()
        for keywords, field in header_keywords:
            if field in used_fields:
                continue
            if any(k in hl for k in keywords):
                mapping[i] = field
                used_fields.add(field)
                break
    # Для ненайденных колонок — распознавание по значениям первой непустой строки
    for i in range(len(headers)):
        if i in mapping:
            continue
        votes: dict[str, int] = {}
        for row in sample_rows[:10]:
            if i < len(row):
                t = detect_field_type(str(row[i]))
                if t and t != "type":
                    votes[t] = votes.get(t, 0) + 1
        if votes:
            best = max(votes, key=votes.get)
            field = {"fio": "user_fio", "device_name": "name", "inventory": "inventory_no",
                     "manufacturer": "manufacturer", "status": "status",
                     "location": "location", "ip": "ip", "mac": "mac"}.get(best)
            if field and field not in used_fields:
                mapping[i] = field
                used_fields.add(field)
    return mapping


def normalize_mac(value: str) -> str:
    """Нормализовать MAC-адрес к виду AA:BB:CC:DD:EE:FF."""
    v = re.sub(r"[^0-9A-Fa-f]", "", value or "")
    if len(v) == 12:
        return ":".join(v[i:i + 2].upper() for i in range(0, 12, 2))
    return (value or "").strip().upper()


def normalize_type(value: str) -> str:
    """Преобразовать текстовое название типа во внутренний код."""
    v = (value or "").strip().lower()
    if v in TYPE_ALIASES:
        return TYPE_ALIASES[v]
    for alias, code in TYPE_ALIASES.items():
        if alias in v:
            return code
    return "computer"


def parse_clipboard_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Разобрать TSV/CSV-текст из буфера обмена на заголовки и строки.

    Автоматически определяет разделитель (табуляция, точка с запятой, запятая).
    """
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return [], []
    first = lines[0]
    if "\t" in first:
        delim = "\t"
    elif ";" in first:
        delim = ";"
    elif "," in first:
        delim = ","
    else:
        delim = "\t"
    rows = [[c.strip() for c in ln.split(delim)] for ln in lines]
    # Считаем первую строку заголовками, если она не похожа на данные
    headers = rows[0]
    data = rows[1:]
    looks_like_header = all(detect_field_type(h) is None for h in headers[: min(4, len(headers))])
    if not looks_like_header:
        headers = [f"Колонка {i + 1}" for i in range(len(rows[0]))]
        data = rows
    return headers, data
