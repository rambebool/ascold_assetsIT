# -*- coding: utf-8 -*-
"""Главное окно AscoldIT: FluentWindow с NavigationInterface слева.

Структура навигации (M1):
  Инфраструктура → Компьютеры, Сетевые МФУ, Принтеры, Телефоны, Периферия, Сетевое
  Склад          → Картриджи, MFP-ремкомплекты, Прочая периферия, Остальное
  Импорт/Экспорт
  Настройки
"""
from PyQt6.QtGui import QFont
from qfluentwidgets import (
    FluentWindow, FluentIcon, InfoBarPosition,
    setTheme, Theme, InfoBar,
)

from app.utils.config import config, APP_NAME, APP_VERSION
from app.ui.pages.asset_list_page import AssetListPage
from app.ui.pages.import_export_page import ImportExportPage
from app.ui.pages.settings_page import SettingsPage


def _icon(name: str, fallback: str = "FOLDER"):
    """Безопасное получение иконки FluentIcon (наборы различаются по версиям)."""
    return getattr(FluentIcon, name, None) or getattr(FluentIcon, fallback)


class MainWindow(FluentWindow):
    """Основное окно приложения в стиле Windows 11 (Fluent Design)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — учёт ИТ-активов")
        self.resize(1360, 820)

        # шрифт Segoe UI Variable (Windows 11), фолбэк Segoe UI
        font = QFont("Segoe UI Variable Text", 10)
        if not QFont("Segoe UI Variable Text").exactMatch():
            font = QFont("Segoe UI", 10)
        self.setFont(font)

        # применяем сохранённую тему
        self._apply_theme(config.get("theme", "auto"))

        # ---------- страницы «Инфраструктура» ----------
        self.pageComputers = AssetListPage("computer", "Компьютеры")
        self.pageMfp = AssetListPage("mfp", "Сетевые МФУ")
        self.pagePrinters = AssetListPage("printer", "Принтеры")
        self.pagePhones = AssetListPage("phone", "Телефоны")
        self.pagePeripheralInfra = AssetListPage("peripheral", "Периферия")
        self.pageNetdev = AssetListPage("netdev", "Сетевое")

        # ---------- страницы «Склад» (M1: отдельные списки без жёсткой привязки к типу) ----------
        self.pageStockCartridges = AssetListPage(None, "Склад: Картриджи")
        self.pageStockMfpKits = AssetListPage(None, "Склад: MFP-ремкомплекты")
        self.pageStockPeriphery = AssetListPage(None, "Склад: Прочая периферия")
        self.pageStockOther = AssetListPage(None, "Склад: Остальное")

        self.pageImportExport = ImportExportPage()
        self.pageSettings = SettingsPage()

        # ---------- навигация слева (NavigationInterface внутри FluentWindow) ----------
        n = self.navigationInterface
        n.setExpandWidth(240)

        item_computers = n.addSubInterface(self.pageComputers, _icon("DEVELOPER_TOOLS", "PC"), "Компьютеры")
        n.addSubInterface(self.pageMfp, _icon("PRINT"), "Сетевые МФУ")
        n.addSubInterface(self.pagePrinters, _icon("PRINT", "FOLDER"), "Принтеры")
        n.addSubInterface(self.pagePhones, _icon("PHONE", "CELL_PHONE"), "Телефоны")
        n.addSubInterface(self.pagePeripheralInfra, _icon("DEVELOPER_TOOLS", "HARD_DRIVE"), "Периферия")
        n.addSubInterface(self.pageNetdev, _icon("WIFI"), "Сетевое")

        n.addSubInterface(self.pageStockCartridges, _icon("BASKET", "SHOPPING_CART"), "Склад: Картриджи")
        n.addSubInterface(self.pageStockMfpKits, _icon("IOT", "UPDATE"), "Склад: MFP-ремкомплекты")
        n.addSubInterface(self.pageStockPeriphery, _icon("HOME"), "Склад: Периферия")
        n.addSubInterface(self.pageStockOther, _icon("DRIVE", "FOLDER"), "Склад: Остальное")

        n.addSubInterface(self.pageImportExport, _icon("SYNC"), "Импорт/Экспорт")
        n.addSubInterface(self.pageSettings, _icon("SETTING"), "Настройки")

        self.navigationInterface.setCurrentItem(item_computers.objectName())

        # связки: импорт на странице «Импорт/Экспорт» обновляет все списки
        self.pageImportExport.imported.connect(self._refresh_all_lists)
        self.pageSettings.themeChanged.connect(self._apply_theme)

        # приветствие
        InfoBar.info(APP_NAME, f"Добро пожаловать! Версия {APP_VERSION}. Файл базы: {config.db_path}",
                     parent=self, position=InfoBarPosition.TOP_RIGHT, duration=5000)

    # ---------- служебное ----------
    def _refresh_all_lists(self) -> None:
        for page in (self.pageComputers, self.pageMfp, self.pagePrinters,
                     self.pagePhones, self.pagePeripheralInfra, self.pageNetdev,
                     self.pageStockCartridges, self.pageStockMfpKits,
                     self.pageStockPeriphery, self.pageStockOther):
            page.refresh()

    @staticmethod
    def _apply_theme(theme: str) -> None:
        """Переключение темы с плавным применением стиля Fluent."""
        mapping = {"auto": Theme.AUTO, "light": Theme.LIGHT, "dark": Theme.DARK}
        setTheme(mapping.get(theme, Theme.AUTO))
