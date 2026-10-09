# -*- coding: utf-8 -*-
"""Страница «Импорт/Экспорт»: все способы загрузки и выгрузки данных в одном месте."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QApplication
from qfluentwidgets import (
    CardWidget, IconWidget, SubtitleLabel, BodyLabel, StrongBodyLabel,
    PrimaryPushButton, PushButton, FluentIcon, InfoBar, InfoBarPosition,
    TextEdit, ComboBox, ProgressBar,
)

from app.models.database import get_db, ASSET_TYPES


class ImportExportPage(QWidget):
    """Центральная страница импорта (Excel/CSV, буфер, AD) и экспорта (CSV/Excel/GLPI)."""

    imported = pyqtSignal()  # чтобы другие страницы обновились

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = get_db()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(14)

        lay.addWidget(SubtitleLabel("Импорт и экспорт данных"))
        hint = BodyLabel("Все операции выполняются локально: без запросов во внешнюю сеть.")
        hint.setTextColor(Qt.GlobalColor.gray)
        lay.addWidget(hint)

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.addWidget(self._card_import_excel(), 0, 0)
        grid.addWidget(self._card_clipboard(), 0, 1)
        grid.addWidget(self._card_ad(), 1, 0)
        grid.addWidget(self._card_export(), 1, 1)
        lay.addLayout(grid)

        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)
        lay.addStretch(1)

        lbl = StrongBodyLabel(f"Всего активов в базе: {len(self.db.get_assets())}")
        lay.addWidget(lbl)

    # ---------- карточки ----------
    def _card_base(self, icon: FluentIcon, title: str, desc: str) -> tuple[CardWidget, QVBoxLayout]:
        card = CardWidget()
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)
        head = QHBoxLayout()
        iw = IconWidget(icon)
        iw.setFixedSize(24, 24)
        head.addWidget(iw)
        head.addWidget(SubtitleLabel(title))
        head.addStretch(1)
        v.addLayout(head)
        d = BodyLabel(desc)
        d.setWordWrap(True)
        d.setTextColor(Qt.GlobalColor.gray)
        v.addWidget(d)
        return card, v

    def _card_import_excel(self) -> CardWidget:
        card, v = self._card_base(
            FluentIcon.DOCUMENT, "Импорт из Excel / CSV",
            "Файлы .xlsx, .xls, .csv. Диалог маппинга колонок с автоопределением "
            "и предпросмотром первых 10 строк.")
        btn = PrimaryPushButton(FluentIcon.FOLDER_ADD, "Импорт из Excel…")
        btn.clicked.connect(self._import_excel)
        v.addWidget(btn)
        return card

    def _card_clipboard(self) -> CardWidget:
        card, v = self._card_base(
            FluentIcon.PASTE, "Вставка из буфера обмена",
            "Скопируйте диапазон ячеек в Excel (Ctrl+C) и нажмите «Распознать». "
            "Поля определяются автоматически (IP, MAC, ФИО,…)")
        self.clipEdit = TextEdit()
        self.clipEdit.setPlaceholderText("Вставьте сюда таблицу из Excel…")
        self.clipEdit.setMaximumHeight(120)
        v.addWidget(self.clipEdit)
        row = QHBoxLayout()
        btnPaste = PushButton(FluentIcon.PASTE, "Взять из буфера")
        btnPaste.clicked.connect(lambda: self.clipEdit.setPlainText(
            QApplication.clipboard().text()))
        btnRec = PrimaryPushButton(FluentIcon.ZOOM, "Распознать и импортировать")
        btnRec.clicked.connect(self._import_clipboard)
        row.addWidget(btnPaste)
        row.addStretch(1)
        row.addWidget(btnRec)
        v.addLayout(row)
        return card

    def _card_ad(self) -> CardWidget:
        card, v = self._card_base(
            FluentIcon.GLOBE, "Импорт из Active Directory",
            "Чтение компьютеров и пользователей домена (только чтение, локальная сеть).")
        row = QHBoxLayout()
        self.cbAdWhat = ComboBox()
        self.cbAdWhat.addItem("Компьютеры", userData="computers")
        self.cbAdWhat.addItem("Пользователи", userData="users")
        btnAd = PrimaryPushButton(FluentIcon.DOWN, "Импорт из AD…")
        btnAd.clicked.connect(self._import_ad)
        row.addWidget(self.cbAdWhat)
        row.addStretch(1)
        row.addWidget(btnAd)
        v.addLayout(row)
        return card

    def _card_export(self) -> CardWidget:
        card, v = self._card_base(
            FluentIcon.SAVE_AS, "Экспорт данных",
            "Выгрузка активов в Excel, CSV или формате импорта GLPI (Computer).")
        self.cbExpType = ComboBox()
        self.cbExpType.addItem("Все активы", userData=None)
        for code, label in ASSET_TYPES.items():
            self.cbExpType.addItem(label, userData=code)
        v.addWidget(self.cbExpType)
        row = QHBoxLayout()
        b1 = PushButton(FluentIcon.DOCUMENT, "Excel")
        b1.clicked.connect(lambda: self._export("excel"))
        b2 = PushButton(FluentIcon.FOLDER, "CSV")
        b2.clicked.connect(lambda: self._export("csv"))
        b3 = PrimaryPushButton(FluentIcon.SHARE, "Экспорт для GLPI")
        b3.clicked.connect(lambda: self._export("glpi"))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)
        row.addWidget(b3)
        v.addLayout(row)
        return card

    # ---------- действия ----------
    def _import_excel(self) -> None:
        from qfluentwidgets import FileDialog
        dlg = FileDialog(self)
        dlg.fileSelected.connect(self._do_import_file)
        dlg.setNameFilter("Таблицы (*.xlsx *.xls *.csv)")
        dlg.open()

    def _do_import_file(self, path: str) -> None:
        if not path:
            return
        from app.services.import_service import ImportService
        try:
            headers, rows = ImportService().read_file(path)
        except Exception as e:
            InfoBar.error("Ошибка чтения файла", str(e), parent=self,
                          position=InfoBarPosition.TOP, duration=6000)
            return
        self._open_mapping(headers, rows)

    def _import_clipboard(self) -> None:
        from app.utils.helpers import parse_clipboard_table
        headers, rows = parse_clipboard_table(self.clipEdit.toPlainText())
        if not rows:
            InfoBar.warning("Не распознано", "Текст не похож на таблицу.", parent=self,
                            position=InfoBarPosition.TOP, duration=4000)
            return
        self._open_mapping(headers, rows)

    def _open_mapping(self, headers: list[str], rows: list[list[str]]) -> None:
        from app.services.import_service import ImportService
        from app.ui.widgets.mapping_dialog import MappingDialog
        suggested = ImportService.suggest_mapping(headers, rows)
        dlg = MappingDialog(headers, rows, suggested, default_type="computer",
                            parent=self.window())
        dlg.finished.connect(self._on_imported)
        dlg.show()

    def _on_imported(self, stats: dict) -> None:
        InfoBar.success("Импорт завершён",
                        f"Создано: {stats['created']}, обновлено: {stats['updated']}, "
                        f"пропущено: {stats['skipped']}.",
                        parent=self, position=InfoBarPosition.TOP, duration=5000)
        self.imported.emit()

    def _import_ad(self) -> None:
        what = self.cbAdWhat.currentData()
        if what == "computers":
            from app.ui.widgets.ad_import_dialog import AdImportDialog
            dlg = AdImportDialog(parent=self)
            dlg.imported.connect(lambda _s: self.imported.emit())
            dlg.exec()
        else:
            self.progress.setVisible(True)
            self.progress.setValue(10)
            QApplication.processEvents()
            try:
                from app.services.ad_service import ADService
                users = ADService().get_users()
                n = ImportCount = None
                from app.services.import_service import ImportService
                n = ImportService().import_ad_users(users)
                self.progress.setValue(100)
                InfoBar.success("AD", f"Импортировано пользователей: {n}.", parent=self,
                                 position=InfoBarPosition.TOP, duration=5000)
            except Exception as e:
                InfoBar.error("AD недоступен", str(e), parent=self,
                              position=InfoBarPosition.TOP, duration=6000)
            finally:
                self.progress.setVisible(False)

    def _export(self, kind: str) -> None:
        from qfluentwidgets import FileDialog, FileSelectionMode
        from app.services.export_service import ExportService
        atype = self.cbExpType.currentData()
        ext = "xlsx" if kind == "excel" else "csv"
        dlg = FileDialog(self, FileSelectionMode.SAVE)
        dlg.setDefaultFileName(ExportService.suggest_filename(ext, atype))
        dlg.setNameFilter(f"{'Excel' if kind == 'excel' else 'CSV'} (*.{ext})")
        dlg.fileSelected.connect(lambda path, k=kind, t=atype: self._do_export(k, t, path))
        dlg.open()

    def _do_export(self, kind: str, atype: str | None, path: str) -> None:
        if not path:
            return
        from app.services.export_service import ExportService
        svc = ExportService()
        try:
            if kind == "excel":
                n = svc.export_excel(path, atype)
            elif kind == "csv":
                n = svc.export_csv(path, atype)
            else:
                n = svc.export_glpi(path, atype or "computer")
            InfoBar.success("Экспорт выполнен", f"Выгружено записей: {n}.\nФайл: {path}",
                            parent=self, position=InfoBarPosition.TOP, duration=6000)
        except Exception as e:
            InfoBar.error("Ошибка экспорта", str(e), parent=self,
                          position=InfoBarPosition.TOP, duration=6000)
