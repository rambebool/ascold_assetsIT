# -*- coding: utf-8 -*-
"""Диалог маппинга колонок источника → поля программы, с предпросмотром и ProgressBar."""
from app.utils.qt_compat import QHBoxLayout, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget, Qt, pyqtSignal
from qfluentwidgets import (
    MaskDialogBase, ComboBox, TableWidget, PushButton, PrimaryPushButton,
    ProgressBar, BodyLabel, FluentIcon, InfoBar, InfoBarPosition, LineEdit,
)

from app.utils.helpers import FIELD_LABELS


class MappingDialog(MaskDialogBase):
    """ Диалог: «Колонка Excel/буфера → Поле программы» + предпросмотр 10 строк."""

    # сигнал завершения импорта: dict(stats)
    finished = pyqtSignal(dict)

    def __init__(self, headers: list[str], rows: list[list[str]],
                 suggested: dict[int, str], default_type: str = "computer",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.headers = headers
        self.rows = rows
        self.default_type = default_type
        self._combos: list[ComboBox] = []

        self.widget.setFixedSize(900, 640)
        self.widget.move((self.width() - 900) // 2, (self.height() - 640) // 2)
        lay = QVBoxLayout(self.widget)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)

        title = BodyLabel("Маппинг колонок: выберите, какие колонки источника в какие поля программы записывать")
        title.setStyleSheet("font-weight: 600; font-size: 15px;")
        lay.addWidget(title)

        # --- блок ComboBox'ов маппинга ---
        map_lay = QVBoxLayout()
        map_lay.setSpacing(4)
        for i, h in enumerate(headers):
            row_lay = QHBoxLayout()
            lbl = BodyLabel(f"Колонка: {h}")
            lbl.setMinimumWidth(260)
            cb = ComboBox()
            cb.addItem("— не импортировать —", userData="")
            for key, label in FIELD_LABELS.items():
                cb.addItem(label, userData=key)
            target = suggested.get(i, "")
            idx = cb.findData(target)
            if idx >= 0:
                cb.setCurrentIndex(idx)
            self._combos.append(cb)
            row_lay.addWidget(lbl)
            row_lay.addWidget(cb, 1)
            map_lay.addLayout(row_lay)
        lay.addLayout(map_lay)

        # --- предпросмотр 10 строк ---
        preview_title = BodyLabel("Предпросмотр первых 10 строк:")
        lay.addWidget(preview_title)
        self.preview = TableWidget(self.widget)
        self.preview.setColumnCount(len(headers))
        self.preview.setHorizontalHeaderLabels(headers)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.preview.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        self.preview.wordWrap = False
        nrows = min(10, len(rows))
        self.preview.setRowCount(nrows)
        for r in range(nrows):
            for c in range(len(headers)):
                val = rows[r][c] if c < len(rows[r]) else ""
                self.preview.setItem(r, c, QTableWidgetItem(str(val)))
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        lay.addWidget(self.preview, 1)

        # --- прогресс + кнопки ---
        self.progress = ProgressBar(self.widget)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        btns = QHBoxLayout()
        self.autoBtn = PushButton(FluentIcon.SYNC, "Автоопределить", self.widget)
        self.autoBtn.clicked.connect(self._auto_detect)
        self.importBtn = PrimaryPushButton(FluentIcon.DOWN, "Импортировать", self.widget)
        self.importBtn.clicked.connect(self._on_import)
        self.cancelBtn = PushButton(FluentIcon.CLOSE, "Отмена", self.widget)
        self.cancelBtn.clicked.connect(self.close)
        btns.addWidget(self.autoBtn)
        btns.addStretch(1)
        btns.addWidget(self.cancelBtn)
        btns.addWidget(self.importBtn)
        lay.addLayout(btns)

    # ---------- логика ----------
    def get_mapping(self) -> dict[int, str]:
        result: dict[int, str] = {}
        for i, cb in enumerate(self._combos):
            field = cb.currentData()
            if field:
                result[i] = field
        return result

    def _auto_detect(self) -> None:
        from app.utils.helpers import guess_mapping
        suggested = guess_mapping(self.headers, self.rows)
        for i, cb in enumerate(self._combos):
            idx = cb.findData(suggested.get(i, ""))
            cb.setCurrentIndex(max(idx, 0))
        InfoBar.success("Готово", "Маппинг определён автоматически",
                        parent=self.widget, position=InfoBarPosition.TOP, duration=2000)

    def _on_import(self) -> None:
        mapping = self.get_mapping()
        if "name" not in mapping.values():
            InfoBar.warning("Нет поля", "Выберите колонку для поля «Имя актива» — без неё импорт невозможен.",
                            parent=self.widget, position=InfoBarPosition.TOP, duration=4000)
            return
        self.progress.setVisible(True)
        self.progress.setValue(0)
        from app.services.import_service import ImportService
        svc = ImportService()
        stats = svc.import_dataset(self.headers, self.rows, mapping,
                                   default_type=self.default_type,
                                   progress=lambda done, total: self._update_progress(done, total))
        self.finished.emit(stats)

    def _update_progress(self, done: int, total: int) -> None:
        self.progress.setValue(int(done / max(total, 1) * 100))
