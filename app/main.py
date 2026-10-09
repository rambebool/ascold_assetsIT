# -*- coding: utf-8 -*-
"""AscoldIT — точка входа десктопного приложения учёта ИТ-активов.

Запуск:  python app/main.py
Требования: PyQt6, PyQt-Fluent-Widgets (интерфейс Windows 11 / Fluent Design).
Офлайн: приложение не выполняет запросов во внешнюю сеть.
"""
import sys
from pathlib import Path

# Позволять запуск как `python app/main.py` — добавляем корень проекта в sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from qfluentwidgets import setTheme, Theme


def apply_theme(theme_name: str) -> None:
    """Применить тему оформления (auto/light/dark)."""
    mapping = {"auto": Theme.AUTO, "light": Theme.LIGHT, "dark": Theme.DARK}
    setTheme(mapping.get(theme_name, Theme.AUTO))


def main() -> int:
    # высоко DPI — как в нативных приложениях Windows 11
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("AscoldIT")
    app.setOrganizationName("AscoldIT")

    # глобальный шрифт Segoe UI Variable (Windows 11)
    font = QFont("Segoe UI Variable Text", 10)
    if not QFont("Segoe UI Variable Text").exactMatch():
        font = QFont("Segoe UI", 10)
    app.setFont(font)

    # конфиг и БД создаются при первом запуске в %APPDATA%\AscoldIT\
    from app.utils.config import config
    apply_theme(config.get("theme", "auto"))

    from app.models.database import get_db
    get_db()  # инициализация assets.db со схемой M1

    from app.ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
