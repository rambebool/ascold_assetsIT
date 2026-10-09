# -*- coding: utf-8 -*-
"""Сервис чтения Active Directory через pywin32 (LDAP/ADODB).

ВАЖНО: только ЧТЕНИЕ (компьютеры, пользователи, группы). Никаких записей в AD.
Работает в офлайне — только обращение к контроллеру домена в локальной сети.
"""
from typing import Optional

from app.utils.config import config


class ADServiceError(Exception):
    """Ошибка подключения/запроса к AD."""


class ADService:
    """Чтение данных из Active Directory (только read-only)."""

    def __init__(self) -> None:
        self.server: str = config.get("ad.server", "") or ""
        self.domain: str = config.get("ad.domain", "") or ""
        self.base_dn: str = config.get("ad.base_dn", "") or ""
        self.username: str = config.get("ad.username", "") or ""
        self.password: str = config.get("ad.password", "") or ""
        self.use_current_user: bool = bool(config.get("ad.use_current_user", True))

    # ---------- проверка доступности ----------
    @staticmethod
    def is_available() -> bool:
        """Доступен ли pywin32 (Windows) для работы с AD."""
        try:
            import win32com.client  # noqa: F401
            return True
        except Exception:
            return False

    def _connection_string(self) -> str:
        if self.server:
            root = f"LDAP://{self.server}"
        elif self.domain:
            root = f"LDAP://{self.domain}"
        else:
            root = "LDAP://"  # binding to current domain
        if self.base_dn:
            root += f"/{self.base_dn}"
        return root

    def _open(self):
        """Открыть ADO-соединение к AD (только чтение)."""
        try:
            import win32com.client
        except ImportError as e:
            raise ADServiceError(
                "pywin32 не установлен или приложение запущено не в Windows. "
                "Импорт из AD доступен только на рабочих станциях в домене."
            ) from e
        conn = win32com.client.Dispatch("ADODB.Connection")
        conn.Provider = "ADSDSOObject"
        conn.Properties["User ID"] = self.username if not self.use_current_user else ""
        conn.Properties["Passwd"] = self.password if not self.use_current_user else ""
        conn.Properties["Ads Provider"] = "ADS"
        try:
            conn.Open("AD Search")
        except Exception as e:
            raise ADServiceError(f"Не удалось подключиться к AD: {e}") from e
        return conn

    def get_computers(self) -> list[dict]:
        """Список компьютеров домена: [{name, os, ip?, dn}]. Только чтение."""
        return self._search(
            "(&(objectCategory=computer)(objectClass=computer))",
            ["name", "dNSHostName", "operatingSystem", "operatingSystemVersion",
             "whenCreated", "description"],
            lambda r: {
                "name": _attr(r, "name"),
                "dns": _attr(r, "dNSHostName"),
                "os": _attr(r, "operatingSystem"),
                "os_version": _attr(r, "operatingSystemVersion"),
                "created": _attr(r, "whenCreated"),
                "description": _attr(r, "description"),
            },
        )

    def get_users(self) -> list[dict]:
        """Список пользователей домена: [{fio, login, department, phone}]."""
        return self._search(
            "(&(objectCategory=person)(objectClass=user)(!userAccountControl:1.2.840.113556.1.4.803:=2))",
            ["name", "sAMAccountName", "displayName", "department", "telephoneNumber"],
            lambda r: {
                "fio": _attr(r, "displayName") or _attr(r, "name"),
                "login": _attr(r, "sAMAccountName"),
                "department": _attr(r, "department"),
                "phone": _attr(r, "telephoneNumber"),
            },
        )

    def get_groups(self) -> list[dict]:
        """Список групп домена."""
        return self._search(
            "(objectCategory=group)",
            ["name", "distinguishedName", "description"],
            lambda r: {
                "name": _attr(r, "name"),
                "dn": _attr(r, "distinguishedName"),
                "description": _attr(r, "description"),
            },
        )

    def test_connection(self) -> str:
        """Проверить подключение. Возвращает текст результата (для InfoBar)."""
        if not self.is_available():
            return "pywin32 недоступен: импорт из AD работает только в Windows."
        try:
            comps = self.get_computers()
            return f"Подключение к AD успешно. Найдено компьютеров: {len(comps)}."
        except ADServiceError as e:
            return str(e)

    # ---------- внутренний поиск ----------
    def _search(self, ldap_filter: str, attributes: list[str], mapper) -> list[dict]:
        import win32com.client
        conn = self._open()
        rs = win32com.client.Dispatch("ADODB.Recordset")
        base = self._connection_string()
        scope = "subtree" if self.base_dn else ""
        query = f"<{base}>;{ldap_filter};{','.join(attributes)}" + (f";{scope}" if scope else "")
        try:
            rs.Open(query, conn, 3, 1)  # adOpenStatic, adLockReadOnly — ТОЛЬКО ЧТЕНИЕ
            out: list[dict] = []
            while not rs.EOF:
                try:
                    out.append(mapper(rs))
                except Exception:
                    pass
                rs.MoveNext()
            rs.Close()
            conn.Close()
            return out
        except Exception as e:
            raise ADServiceError(f"Ошибка запроса к AD: {e}") from e


def _attr(recordset, name: str) -> str:
    """Безопасное чтение атрибута из ADODB.Recordset."""
    try:
        v = recordset.Fields(name).Value
        return str(v) if v is not None else ""
    except Exception:
        return ""


def parse_fio_from_ad(display_name: str, default_login: str = "") -> tuple[str, str]:
    """Из displayName 'Иванов Иван Иванович' вывести (ФИО, предполагаемый логин)."""
    fio = (display_name or "").strip()
    parts = fio.split()
    login = default_login
    if not login and len(parts) >= 2:
        login = (parts[0][:1] + parts[1][:1]).lower()
    return fio, login
