# -*- coding: utf-8 -*-
"""Кастомные виджеты AscoldIT: модель TableModel для TableView."""
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from qfluentwidgets import FluentIcon

# Описание колонки: (ключ, заголовок, ширина)
ColumnDef = tuple[str, str, int]


class AssetTableModel(QAbstractTableModel):
    """Модель таблицы активов для qfluentwidgets.TableView."""

    def __init__(self, columns: list[ColumnDef], rows: list[dict] | None = None) -> None:
        super().__init__()
        self.columns = columns
        self.rows: list[dict] = rows or []
        # Иконки статусов (Segoe Fluent Icons через FluentIcon)
        self._status_icons = {
            "Эксплуатируется": FluentIcon.ACCEPT,
            "В резерве": FluentIcon.INFO,
            "На ремонте": FluentIcon.SYNC,
            "Списан": FluentIcon.CLOSE,
            "Не проверено": FluentIcon.HELP,
        }

    # ---------- данные ----------
    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def get_row(self, row: int) -> dict:
        return self.rows[row]

    # ---------- интерфейсы модели ----------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        key, _, _ = self.columns[index.column()]
        row = self.rows[index.row()]
        value = row.get(key, "")
        if value is None:
            value = ""
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if key == "type":
                from app.models.database import ASSET_TYPES
                return ASSET_TYPES.get(value, value)
            return str(value)
        if role == Qt.ItemDataRole.DecorationRole and key == "status":
            return self._status_icons.get(str(value), FluentIcon.INFO).icon()
        return None

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.columns[section][1]
            return str(section + 1)
        return None
