# -*- coding: utf-8 -*-
"""Страница списка активов: TableView + топбар (Добавить/Импорт/Экспорт/AD/Фильтры/Поиск).

Универсальна для всех категорий (Компьютеры, МФУ, Принтеры, …, Склад).
"""
import os
from PyQt6.QtCore import Qt, QSortFilterProxyModel, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QHeaderView, QApplication,
)
from qfluentwidgets import (
    TableView, PushButton, PrimaryPushButton, SearchLineEdit, FluentIcon,
    InfoBar, InfoBarPosition, ComboBox, RoundMenu, Action, MessageBox,
    BodyLabel,
)

from app.models.database import get_db, ASSET_TYPES, ASSET_STATUSES
from app.ui.widgets.asset_table import AssetTableModel
from app.ui.widgets.asset_dialog import AssetDialog
from app.ui.widgets.mapping_dialog import MappingDialog
from app.ui.widgets.ad_import_dialog import AdImportDialog


class AssetListPage(QWidget):
    """Список активов одного типа (или «все») с полным набором действий."""

    # Колонки таблицы по спецификации M1
    COLUMNS = [
        ("name", "Имя", 200),
        ("ip", "IP", 120),
        ("mac", "MAC", 140),
        ("user_fio", "Пользователь", 170),
        ("location", "Местоположение", 170),
        ("status", "Статус", 150),
        ("updated_at", "Последнее обновление", 160),
    ]

    def __init__(self, asset_type: str | None = None, title: str = "Активы", parent=None):
        super().__init__(parent)
        self.asset_type = asset_type   # None => все активы
        self.page_title = title
        self.db = get_db()
        self._search_text = ""
        self._status_filter = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(12)

        # ---------- топбар ----------
        topbar = QHBoxLayout()
        topbar.setSpacing(8)
        self.btnAdd = PrimaryPushButton(FluentIcon.ADD, "Добавить")
        self.btnAdd.clicked.connect(self._add_asset)
        self.btnImport = PushButton(FluentIcon.FOLDER_ADD, "Импорт")
        self.btnImport.clicked.connect(self._show_import_menu)
        self.btnExport = PushButton(FluentIcon.SAVE_AS, "Экспорт")
        self.btnExport.clicked.connect(self._show_export_menu)
        self.btnAd = PushButton(FluentIcon.GLOBE, "Обновить из AD")
        self.btnAd.clicked.connect(self._ad_import)
        self.btnFilters = PushButton(FluentIcon.FILTER, "Фильтры")
        self.btnFilters.clicked.connect(self._show_filter_menu)

        self.lblFilter = BodyLabel("")
        self.lblFilter.setTextColor(Qt.GlobalColor.gray)

        self.search = SearchLineEdit()
        self.search.setPlaceholderText("Поиск: имя, IP, MAC, пользователь…")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(self._on_search)

        for b in (self.btnAdd, self.btnImport, self.btnExport, self.btnAd, self.btnFilters):
            topbar.addWidget(b)
        topbar.addStretch(1)
        topbar.addWidget(self.lblFilter)
        topbar.addWidget(self.search)
        lay.addLayout(topbar)

        # ---------- таблица ----------
        self.model = AssetTableModel(self.COLUMNS)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.table = TableView(self)
        self.table.setModel(self.proxy)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(TableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(TableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(TableView.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        for i, (_, _, width) in enumerate(self.COLUMNS):
            hh.resizeSection(i, width)
        hh.setStretchLastSection(True)
        self.table.doubleClicked.connect(self._on_double_click)
        lay.addWidget(self.table, 1)

        # счётчик записей
        self.lblCount = BodyLabel("")
        self.lblCount.setTextColor(Qt.GlobalColor.gray)
        lay.addWidget(self.lblCount)

        self.refresh()

    # ---------- данные ----------
    def refresh(self) -> None:
        rows = self.db.get_assets(atype=self.asset_type, status=self._status_filter)
        self.model.set_rows(rows)
        self._apply_search()
        self.lblCount.setText(f"Записей: {len(rows)}"
                              + (f" · категория: {self.page_title}" if self.asset_type else ""))

    def _on_search(self, text: str) -> None:
        self._search_text = text
        self._apply_search()

    def _apply_search(self) -> None:
        self.proxy.setFilterFixedString(self._search_text)

    # ---------- CRUD ----------
    def _add_asset(self) -> None:
        dlg = AssetDialog(asset_id=None, default_type=self.asset_type or "computer", parent=self)
        dlg.saved.connect(lambda _id: self.refresh())
        dlg.exec()

    def _on_double_click(self, index) -> None:
        src = self.proxy.mapToSource(index)
        row = self.model.get_row(src.row())
        dlg = AssetDialog(asset_id=int(row["id"]), parent=self)
        dlg.saved.connect(lambda _id: self.refresh())
        dlg.deleted.connect(lambda _id: self.refresh())
        dlg.exec()

    # ---------- импорт ----------
    def _show_import_menu(self) -> None:
        menu = RoundMenu(parent=self)
        act_excel = Action(FluentIcon.EXCEL, "Импорт из Excel / CSV…")
        act_excel.triggered.connect(self._import_excel)
        act_clip = Action(FluentIcon.PASTE, "Вставить из буфера обмена…")
        act_clip.triggered.connect(self._import_clipboard)
        act_ad = Action(FluentIcon.GLOBE, "Импорт из Active Directory…")
        act_ad.triggered.connect(self._ad_import)
        menu.addAction(act_excel)
        menu.addAction(act_clip)
        menu.addAction(act_ad)
        menu.exec(self.mapToGlobal(self.btnImport.rect().bottomLeft()))

    def _import_excel(self) -> None:
        from qfluentwidgets import FileDialog, FileSelectionMode
        dlg = FileDialog(self)
        dlg.fileSelected.connect(self._do_import_file)
        dlg.setNameFilter("Таблицы (*.xlsx *.xls *.csv)")
        dlg.open()

    def _do_import_file(self, path: str) -> None:
        if not path:
            return
        try:
            from app.services.import_service import ImportService
            svc = ImportService()
            headers, rows = svc.read_file(path)
        except Exception as e:
            InfoBar.error("Ошибка чтения файла", str(e), parent=self,
                          position=InfoBarPosition.TOP, duration=6000)
            return
        self._open_mapping(headers, rows)

    def _import_clipboard(self) -> None:
        dlg = ClipboardImportDialog(parent=self)
        dlg.dataReady.connect(lambda hr: self._open_mapping(hr[0], hr[1]))
        dlg.exec()

    def _open_mapping(self, headers: list[str], rows: list[list[str]]) -> None:
        if not headers or not rows:
            InfoBar.warning("Пусто", "Источник не содержит данных.", parent=self,
                            position=InfoBarPosition.TOP, duration=4000)
            return
        from app.services.import_service import ImportService
        suggested = ImportService.suggest_mapping(headers, rows)
        dlg = MappingDialog(headers, rows, suggested,
                            default_type=self.asset_type or "computer", parent=self.window())
        dlg.finished.connect(self._on_imported)
        dlg.show()

    def _on_imported(self, stats: dict) -> None:
        self.refresh()
        errors = stats.get("errors") or []
        msg = (f"Создано: {stats['created']}, обновлено: {stats['updated']}, "
               f"пропущено: {stats['skipped']}.")
        if errors:
            InfoBar.warning("Импорт с замечаниями", msg + " Ошибки: " + "; ".join(errors[:3]),
                            parent=self, position=InfoBarPosition.TOP, duration=7000)
        else:
            InfoBar.success("Импорт завершён", msg, parent=self,
                            position=InfoBarPosition.TOP, duration=5000)

    # ---------- экспорт ----------
    def _show_export_menu(self) -> None:
        menu = RoundMenu(parent=self)
        for icon, label, kind in (
            (FluentIcon.SAVE_AS, "Экспорт в Excel (.xlsx)…", "excel"),
            (FluentIcon.FOLDER, "Экспорт в CSV (.csv)…", "csv"),
            (FluentIcon.SHARE, "Экспорт для GLPI (.csv)…", "glpi"),
        ):
            act = Action(icon, label)
            act.triggered.connect(lambda checked=False, k=kind: self._export(k))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(self.btnExport.rect().bottomLeft()))

    def _export(self, kind: str) -> None:
        from qfluentwidgets import FileDialog, FileSelectionMode
        from app.services.export_service import ExportService
        ext = "xlsx" if kind == "excel" else "csv"
        dlg = FileDialog(self, FileSelectionMode.SAVE)
        name = ExportService.suggest_filename(ext, self.asset_type)
        dlg.setDefaultFileName(name)
        dlg.setNameFilter(f"{'Excel' if kind == 'excel' else 'CSV'} (*.{ext})")
        dlg.fileSelected.connect(lambda path, k=kind: self._do_export(k, path))
        dlg.open()

    def _do_export(self, kind: str, path: str) -> None:
        if not path:
            return
        from app.services.export_service import ExportService
        svc = ExportService()
        try:
            if kind == "excel":
                n = svc.export_excel(path, self.asset_type)
            elif kind == "csv":
                n = svc.export_csv(path, self.asset_type)
            else:
                n = svc.export_glpi(path, self.asset_type or "computer")
            InfoBar.success("Экспорт выполнен",
                            f"Выгружено записей: {n}.\nФайл: {path}",
                            parent=self, position=InfoBarPosition.TOP, duration=6000)
        except Exception as e:
            InfoBar.error("Ошибка экспорта", str(e), parent=self,
                          position=InfoBarPosition.TOP, duration=6000)

    # ---------- AD ----------
    def _ad_import(self) -> None:
        dlg = AdImportDialog(parent=self)
        dlg.imported.connect(lambda stats: (self.refresh(), InfoBar.success(
            "AD-импорт", f"Создано: {stats['created']}, обновлено: {stats['updated']}.",
            parent=self, position=InfoBarPosition.TOP, duration=5000)))
        dlg.exec()

    # ---------- фильтры ----------
    def _show_filter_menu(self) -> None:
        menu = RoundMenu(parent=self)
        act_all = Action(FluentIcon.CANCEL, "Сбросить фильтр статуса")
        act_all.triggered.connect(lambda: self._set_status(""))
        menu.addAction(act_all)
        menu.addSeparator()
        for st in ASSET_STATUSES:
            act = Action(FluentIcon.FILTER, f"Статус: {st}")
            act.triggered.connect(lambda checked=False, s=st: self._set_status(s))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(self.btnFilters.rect().bottomLeft()))

    def _set_status(self, status: str) -> None:
        self._status_filter = status
        self.lblFilter.setText(f"Фильтр: {status}" if status else "")
        self.refresh()


class ClipboardImportDialog(QDialog):
    """Диалог «Вставить из буфера»: TextEdit → Распознать → предпросмотр → маппинг."""

    dataReady = pyqtSignal(object)  # (headers, rows)

    def __init__(self, parent=None):
        super().__init__(parent)
        from qfluentwidgets import TextEdit as FTextEdit
        self.setWindowTitle("Вставить из буфера обмена — AscoldIT")
        self.resize(760, 480)
        lay = QVBoxLayout(self)
        lbl = BodyLabel("Вставьте данные из Excel (Ctrl+V) или наберите таблицу. "
                        "Разделители: табуляция, ';' или ','. Первая строка — заголовки.")
        lay.addWidget(lbl)
        self.edit = FTextEdit()
        # авто-вставка из буфера
        cb = QApplication.clipboard().text()
        if cb:
            self.edit.setPlainText(cb)
        lay.addWidget(self.edit, 1)
        btns = QHBoxLayout()
        btnCancel = PushButton(FluentIcon.CLOSE, "Отмена")
        btnCancel.clicked.connect(self.reject)
        btnRecognize = PrimaryPushButton(FluentIcon.ZOOM, "Распознать")
        btnRecognize.clicked.connect(self._recognize)
        btns.addStretch(1)
        btns.addWidget(btnCancel)
        btns.addWidget(btnRecognize)
        lay.addLayout(btns)

    def _recognize(self) -> None:
        from app.utils.helpers import parse_clipboard_table
        headers, rows = parse_clipboard_table(self.edit.toPlainText())
        if not rows:
            InfoBar.warning("Не распознано", "Не удалось разобрать текст на таблицу.",
                            parent=self, position=InfoBarPosition.TOP, duration=4000)
            return
        self.dataReady.emit((headers, rows))
        self.accept()
