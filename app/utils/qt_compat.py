# -*- coding: utf-8 -*-
"""Единая точка импорта Qt для всего приложения AscoldIT.

Проблема, которую решает этот модуль
------------------------------------
Пакет «PyQt-Fluent-Widgets» без флага ``--compile`` (или установленный из
обычного wheel) содержит исходники на **PyQt5**. Его базовые классы
(FluentWindow и т.д.) наследуются от PyQt5-виджетов. Если при этом
QApplication создан из PyQt6 — получается смешение двух сборок Qt в одном
процессе, что приводит к ошибкам вроде::

    TypeError: QObject(parent: QObject|None = None):
               argument 1 has unexpected type 'MainWindow'

Решение: ВСЕ модули приложения импортируют Qt-классы только отсюда.
Модуль определяет, из какого биндинга собраны qframelesswindow /
qfluentwidgets, и переэкспортирует классы именно этого биндинга.
В корректно настроенном окружении (PyQt6-сборка библиотеки) это PyQt6;
в «битом» окружении приложение продолжит работать на PyQt5-сборке.

ВАЖНО: сам файл не создаёт виджетов — только переэкспорт классов.
"""
import os

os.environ.setdefault("QT_API", "pyqt6")


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
    # если qframelesswindow не импортируется — считаем окружение PyQt6
    return "pyqt6"


BINDING = _detect_binding()

if BINDING == "pyqt5":
    print("[AscoldIT] ВНИМАНИЕ: PyQt-Fluent-Widgets установлен как PyQt5-сборка.\n"
          "           Приложение запустится на PyQt5, но для нативного вида\n"
          "           Windows 11 по ТЗ переустановите PyQt6-сборку:\n"
          '             pip uninstall -y PyQt-Fluent-Widgets && \\\n'
          '             pip install --no-deps --compile "PyQt6-Fluent-Widgets[full]"')
    from PyQt5.QtCore import (          # noqa: F401,F403
        Qt, QObject, QThread, QTimer, QSize, QPoint, QRect,
        QAbstractItemModel, QAbstractTableModel, QSortFilterProxyModel,
        QModelIndex, pyqtSignal, QStringListModel, QEvent,
    )
    from PyQt5.QtGui import (           # noqa: F401,F403
        QFont, QColor, QIcon, QPixmap, QDesktopServices, QKeySequence, QCursor,
    )
    from PyQt5.QtWidgets import (       # noqa: F401,F403
        QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFormLayout, QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
        QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox, QTableView,
        QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
        QStyle, QFileDialog, QMessageBox, QMenu, QSizePolicy, QScrollArea,
        QListWidget, QListWidgetItem, QFrame, QSplitter, QStackedWidget,
        QGroupBox, QPushButton, QToolButton, QAction,
    )
    from PyQt5.QtCore import QUrl       # noqa: F401,F403
else:
    from PyQt6.QtCore import (          # noqa: F401,F403
        Qt, QObject, QThread, QTimer, QSize, QPoint, QRect,
        QAbstractItemModel, QAbstractTableModel, QSortFilterProxyModel,
        QModelIndex, pyqtSignal, QStringListModel, QUrl, QEvent,
    )
    from PyQt6.QtGui import (           # noqa: F401,F403
        QFont, QColor, QIcon, QPixmap, QDesktopServices, QKeySequence, QCursor,
    )
    from PyQt6.QtWidgets import (       # noqa: F401,F403
        QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
        QFormLayout, QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
        QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox, QTableView,
        QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
        QStyle, QFileDialog, QMessageBox, QMenu, QSizePolicy, QScrollArea,
        QListWidget, QListWidgetItem, QFrame, QSplitter, QStackedWidget,
        QGroupBox, QPushButton, QToolButton, QAction,
    )

__all__ = ["BINDING"]


# ---------- кросс-версионные enum-константы (Qt5 ↔ Qt6) ----------
def _ns(name, pairs):
    ns = type(name, (), {})
    for attr, value in pairs:
        setattr(ns, attr, value)
    return ns


if BINDING == "pyqt5":
    # В PyQt5 enum «голые» — создаём пространства имён в стиле Qt6,
    # чтобы один и тот же код работал с обеими сборками библиотеки.
    if not hasattr(Qt, "ItemDataRole"):
        Qt.ItemDataRole = _ns("ItemDataRole", [
            ("DisplayRole", Qt.DisplayRole), ("EditRole", Qt.EditRole),
            ("DecorationRole", Qt.DecorationRole), ("ToolTipRole", Qt.ToolTipRole),
            ("UserRole", Qt.UserRole), ("TextAlignmentRole", Qt.TextAlignmentRole),
            ("BackgroundRole", Qt.BackgroundRole), ("ForegroundRole", Qt.ForegroundRole),
            ("CheckStateRole", Qt.CheckStateRole), ("SizeHintRole", Qt.SizeHintRole),
        ])
    if not hasattr(Qt, "GlobalColor"):
        Qt.GlobalColor = _ns("GlobalColor", [
            ("white", Qt.white), ("black", Qt.black), ("gray", Qt.gray),
            ("darkGray", Qt.darkGray), ("lightGray", Qt.lightGray),
            ("red", Qt.red), ("green", Qt.green), ("blue", Qt.blue),
        ])
    if not hasattr(Qt, "CaseSensitivity"):
        Qt.CaseSensitivity = _ns("CaseSensitivity", [
            ("CaseInsensitive", Qt.CaseInsensitive), ("CaseSensitive", Qt.CaseSensitive)])
    if not hasattr(Qt, "Orientation"):
        Qt.Orientation = _ns("Orientation", [
            ("Horizontal", Qt.Horizontal), ("Vertical", Qt.Vertical)])
    if not hasattr(Qt, "ItemFlag"):
        Qt.ItemFlag = _ns("ItemFlag", [
            ("ItemIsUserCheckable", Qt.ItemIsUserCheckable),
            ("ItemIsEnabled", Qt.ItemIsEnabled),
            ("ItemIsSelectable", Qt.ItemIsSelectable),
            ("ItemIsEditable", Qt.ItemIsEditable), ("NoItemFlags", Qt.NoItemFlags)])
    if not hasattr(Qt, "CheckState"):
        Qt.CheckState = _ns("CheckState", [
            ("Unchecked", Qt.Unchecked), ("PartiallyChecked", Qt.PartiallyChecked),
            ("Checked", Qt.Checked)])
    if not hasattr(Qt, "AlignmentFlag"):
        Qt.AlignmentFlag = _ns("AlignmentFlag", [
            ("AlignLeft", Qt.AlignLeft), ("AlignRight", Qt.AlignRight),
            ("AlignCenter", Qt.AlignCenter), ("AlignTop", Qt.AlignTop),
            ("AlignBottom", Qt.AlignBottom), ("AlignVCenter", Qt.AlignVCenter),
            ("AlignHCenter", Qt.AlignHCenter)])

    from PyQt5.QtWidgets import QHeaderView as _QH, QAbstractItemView as _QAV
    if not hasattr(_QH, "ResizeMode"):
        _QH.ResizeMode = _ns("ResizeMode", [
            ("Interactive", _QH.Interactive), ("Stretch", _QH.Stretch),
            ("Fixed", _QH.Fixed), ("ResizeToContents", _QH.ResizeToContents)])
    if not hasattr(_QAV, "SelectionBehavior"):
        _QAV.SelectionBehavior = _ns("SelectionBehavior", [
            ("SelectRows", _QAV.SelectRows), ("SelectColumns", _QAV.SelectColumns),
            ("SelectItems", _QAV.SelectItems)])
    if not hasattr(_QAV, "SelectionMode"):
        _QAV.SelectionMode = _ns("SelectionMode", [
            ("SingleSelection", _QAV.SingleSelection),
            ("ExtendedSelection", _QAV.ExtendedSelection),
            ("MultiSelection", _QAV.MultiSelection)])
