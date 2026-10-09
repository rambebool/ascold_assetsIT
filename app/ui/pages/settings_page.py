# -*- coding: utf-8 -*-
"""Страница «Настройки»: тема, шрифт, путь к БД, параметры Active Directory."""
from app.utils.qt_compat import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget, Qt, pyqtSignal
from pathlib import Path

from qfluentwidgets import (
    CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel, ComboBox, LineEdit,
    PushButton, PrimaryPushButton, SettingCardGroup, FluentIcon, InfoBar,
    InfoBarPosition, SwitchButton, PasswordLineEdit,
)

from app.utils.config import config, config_dir, default_db_path
from app.models.database import get_db, reinit_db


class SettingsPage(QWidget):
    """Настройки приложения (аналог страницы параметров Windows 11)."""

    themeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(14)

        lay.addWidget(SubtitleLabel("Настройки"))

        # ---------- внешний вид ----------
        card_ui = CardWidget()
        v = QVBoxLayout(card_ui)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)
        v.addWidget(StrongBodyLabel("Внешний вид"))
        row = QHBoxLayout()
        row.addWidget(BodyLabel("Тема оформления:"))
        self.cbTheme = ComboBox()
        self.cbTheme.addItem("Как в системе", userData="auto")
        self.cbTheme.addItem("Светлая", userData="light")
        self.cbTheme.addItem("Тёмная", userData="dark")
        idx = self.cbTheme.findData(config.get("theme", "auto"))
        self.cbTheme.setCurrentIndex(max(idx, 0))
        self.cbTheme.currentIndexChanged.connect(self._on_theme)
        row.addWidget(self.cbTheme)
        row.addStretch(1)
        v.addLayout(row)
        lbl_font = BodyLabel("Шрифт интерфейса: Segoe UI Variable (стандарт Windows 11).")
        lbl_font.setTextColor(Qt.GlobalColor.gray)
        v.addWidget(lbl_font)
        lay.addWidget(card_ui)

        # ---------- база данных ----------
        card_db = CardWidget()
        vd = QVBoxLayout(card_db)
        vd.setContentsMargins(18, 14, 18, 14)
        vd.setSpacing(8)
        vd.addWidget(StrongBodyLabel("База данных (SQLite)"))
        row2 = QHBoxLayout()
        self.edDb = LineEdit(None)
        self.edDb.setText(str(config.db_path))
        self.edDb.setMinimumWidth(380)
        btnBrowse = PushButton(FluentIcon.FOLDER, "Обзор…")
        btnBrowse.clicked.connect(self._browse_db)
        btnSaveDb = PrimaryPushButton(FluentIcon.SAVE, "Применить путь")
        btnSaveDb.clicked.connect(self._apply_db_path)
        row2.addWidget(self.edDb, 1)
        row2.addWidget(btnBrowse)
        row2.addWidget(btnSaveDb)
        vd.addLayout(row2)
        info = BodyLabel(f"Папка конфигурации: {config_dir()}")
        info.setTextColor(Qt.GlobalColor.gray)
        vd.addWidget(info)
        lay.addWidget(card_db)

        # ---------- Active Directory ----------
        card_ad = CardWidget()
        va = QVBoxLayout(card_ad)
        va.setContentsMargins(18, 14, 18, 14)
        va.setSpacing(8)
        va.addWidget(StrongBodyLabel("Active Directory (только чтение)"))

        grid_rows = [
            ("Сервер / контроллер домена:", "ad.server", "dc01.corp.local"),
            ("Домен:", "ad.domain", "corp.local"),
            ("Base DN:", "ad.base_dn", "DC=corp,DC=local"),
            ("Пользователь (пусто = текущий):", "ad.username", ""),
        ]
        self.adEdits: dict[str, LineEdit] = {}
        for label, key, ph in grid_rows:
            r = QHBoxLayout()
            l = BodyLabel(label)
            l.setMinimumWidth(230)
            ed = LineEdit(None)
            ed.setText(str(config.get(key, "") or ""))
            ed.setPlaceholderText(ph)
            ed.editingFinished.connect(lambda k=key, e=ed: self._save_ad(k, e.text()))
            self.adEdits[key] = ed
            r.addWidget(l)
            r.addWidget(ed, 1)
            va.addLayout(r)
        rp = QHBoxLayout()
        lp = BodyLabel("Пароль service-аккаунта:")
        lp.setMinimumWidth(230)
        self.edPass = PasswordLineEdit(None)
        self.edPass.setText(str(config.get("ad.password", "") or ""))
        self.edPass.setPlaceholderText("только для локального хранения")
        self.edPass.editingFinished.connect(lambda: self._save_ad("ad.password", self.edPass.text()))
        rp.addWidget(lp)
        rp.addWidget(self.edPass, 1)
        va.addLayout(rp)

        rs = QHBoxLayout()
        ls = BodyLabel("Использовать текущего пользователя домена:")
        ls.setMinimumWidth(230)
        self.swCurrentUser = SwitchButton()
        self.swCurrentUser.setChecked(bool(config.get("ad.use_current_user", True)))
        self.swCurrentUser.checkedChanged.connect(
            lambda c: self._save_ad("ad.use_current_user", bool(c)))
        rs.addWidget(ls)
        rs.addWidget(self.swCurrentUser)
        rs.addStretch(1)
        va.addLayout(rs)

        btnTest = PushButton(FluentIcon.WIFI, "Проверить подключение к AD")
        btnTest.clicked.connect(self._test_ad)
        va.addWidget(btnTest)
        lay.addWidget(card_ad)

        lay.addStretch(1)

        about = BodyLabel("AscoldIT · M1 · Офлайн-режим: внешних сетевых запросов нет.")
        about.setTextColor(Qt.GlobalColor.gray)
        lay.addWidget(about)

    # ---------- обработчики ----------
    def _on_theme(self) -> None:
        theme = self.cbTheme.currentData()
        config.set("theme", theme)
        config.save()
        self.themeChanged.emit(theme)
        from qfluentwidgets import setTheme, Theme
        mapping = {"auto": Theme.AUTO, "light": Theme.LIGHT, "dark": Theme.DARK}
        setTheme(mapping.get(theme, Theme.AUTO))
        InfoBar.info("Тема", "Оформление переключено.", parent=self,
                     position=InfoBarPosition.TOP, duration=2500)

    def _browse_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Выберите файл базы данных",
                                              str(default_db_path()),
                                              "Базы SQLite (*.db);;Все файлы (*)")
        if path:
            self.edDb.setText(path)

    def _apply_db_path(self) -> None:
        raw = self.edDb.text().strip()
        if not raw:
            return
        p = Path(raw)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            config.set("db_path", str(p))
            config.save()
            reinit_db(p)
            InfoBar.success("База данных", f"Переход на новую базу: {p}", parent=self,
                            position=InfoBarPosition.TOP, duration=4000)
        except Exception as e:
            InfoBar.error("Ошибка", f"Не удалось использовать путь: {e}", parent=self,
                          position=InfoBarPosition.TOP, duration=5000)

    def _save_ad(self, key: str, value) -> None:
        config.set(key, value)
        config.save()

    def _test_ad(self) -> None:
        from app.services.ad_service import ADService
        svc = ADService()
        msg = svc.test_connection()
        if "успешно" in msg.lower():
            InfoBar.success("AD", msg, parent=self, position=InfoBarPosition.TOP, duration=5000)
        else:
            InfoBar.warning("AD", msg, parent=self, position=InfoBarPosition.TOP, duration=7000)
