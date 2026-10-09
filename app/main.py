# -*- coding: utf-8 -*-
"""AscoldIT — точка входа десктопного приложения учёта ИТ-активов.

Запуск:  python app/main.py
Требования: PyQt6, PyQt-Fluent-Widgets (интерфейс Windows 11 / Fluent Design).
Офлайн: приложение не выполняет запросов во внешнюю сеть.
"""
import gc
import os
import sys
from pathlib import Path

# Позволять запуск как `python app/main.py` — добавляем корень проекта в sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Защита от «QWidget: Must construct a QApplication before a QWidget».
# Корень проблемы — НЕ наш код (все виджеты в app/ создаются только внутри
# __init__/функциях, после создания QApplication), а окружение Python:
# пакет PyQt-Fluent-Widgets без флага [--compile] содержит исходники на PyQt5,
# и его базовые классы наследуются от PyQt5-виджетов. Если QApplication при этом
# создан из PyQt6 — Qt аварийно завершает процесс.
# Решение: определяем реальный биндинг qframelesswindow/qfluentwidgets и
# создаём QApplication ИЗ ТОГО ЖЕ биндинга (в корректном окружении это PyQt6).
def _detect_binding() -> str:
    """Определяет, из какого Qt-биндинга построены классы qframelesswindow."""
    try:
        from qframelesswindow import FramelessWindow
        for klass in FramelessWindow.__mro__:
            m = getattr(klass, "__module__", "") or ""
            if m.startswith("PyQt5"):
                return "pyqt5"
            if m.startswith("PyQt6"):
                return "pyqt6"
    except Exception:
        pass
    # если qframelesswindow не импортируется — считаем окружение PyQt6-совместимым
    return "pyqt6"


os.environ.setdefault("QT_API", "pyqt6")

_QT_BINDING = _detect_binding()

if _QT_BINDING == "pyqt5":
    # Неверная установка библиотеки (без --compile): чтобы приложение всё же
    # запустилось, предупреждаем и используем тот же биндинг, что и библиотека.
    print("[AscoldIT] ВНИМАНИЕ: PyQt-Fluent-Widgets установлен без флага "
          "[--compile] (PyQt5-сборка). Переустановите корректно:\n"
          '    pip uninstall -y PyQt-Fluent-Widgets && pip install --no-deps '
          '--compile "PyQt6-Fluent-Widgets[full]"')
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication
else:
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
    if _QT_BINDING == "pyqt6":
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    else:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # ВАЖНО: QApplication создаётся ДО импорта любых модулей интерфейса,
    # потому что qfluentwidgets/qframelesswindow могут создавать виджеты
    # на уровне импорта модуля. Все страницы импортируются только здесь,
    # после создания приложения.
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
