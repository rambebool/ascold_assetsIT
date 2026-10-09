# -*- coding: utf-8 -*-
"""Диалог импорта компьютеров из Active Directory (только чтение).

Список компьютеров домена с CheckBox'ами → выбор → импорт выбранных в БД.
"""
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidgetItem
from qfluentwidgets import (
    ListWidget, PushButton, PrimaryPushButton, FluentIcon, BodyLabel,
    ProgressBar, InfoBar, InfoBarPosition, SearchLineEdit, SubtitleLabel,
)


class _AdFetchWorker(QObject):
    """Фоновое получение списка компьютеров из AD (чтобы не вешать UI)."""
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            from app.services.ad_service import ADService
            svc = ADService()
            self.done.emit(svc.get_computers())
        except Exception as e:
            self.error.emit(str(e))


class AdImportDialog(QDialog):
    """Импорт компьютеров из AD: список с чекбоксами + поиск + прогресс."""

    imported = pyqtSignal(dict)  # stats

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Импорт из Active Directory — AscoldIT")
        self.resize(640, 560)
        self.computers: list[dict] = []
        self._thread: QThread | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(SubtitleLabel("Компьютеры домена"))
        head.addStretch(1)
        self.btnRefresh = PushButton(FluentIcon.SYNC, "Загрузить заново")
        self.btnRefresh.clicked.connect(self._load)
        head.addWidget(self.btnRefresh)
        lay.addLayout(head)

        info = BodyLabel("Чтение AD (только чтение). Отметьте компьютеры для импорта.")
        info.setTextColor(Qt.GlobalColor.gray)
        lay.addWidget(info)

        self.search = SearchLineEdit()
        self.search.setPlaceholderText("Поиск по имени…")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        self.list = ListWidget()
        lay.addWidget(self.list, 1)

        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        btns = QHBoxLayout()
        self.btnAll = PushButton(FluentIcon.CHECKBOX, "Выделить все")
        self.btnAll.clicked.connect(lambda: self._check_all(True))
        self.btnNone = PushButton(FluentIcon.CANCEL, "Снять выделение")
        self.btnNone.clicked.connect(lambda: self._check_all(False))
        self.btnCancel = PushButton(FluentIcon.CLOSE, "Отмена")
        self.btnCancel.clicked.connect(self.reject)
        self.btnImport = PrimaryPushButton(FluentIcon.DOWN, "Импортировать выбранные")
        self.btnImport.clicked.connect(self._import)
        btns.addWidget(self.btnAll)
        btns.addWidget(self.btnNone)
        btns.addStretch(1)
        btns.addWidget(self.btnCancel)
        btns.addWidget(self.btnImport)
        lay.addLayout(btns)

        self._load()

    # ---------- загрузка AD ----------
    def _load(self) -> None:
        self.list.clear()
        self.list.addItem(QListWidgetItem("Загрузка списка компьютеров из AD…"))
        thread = QThread(self)
        worker = _AdFetchWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(self._on_loaded)
        worker.error.connect(self._on_error)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        self._thread = thread
        thread.start()

    def _on_loaded(self, computers: list) -> None:
        self.computers = computers
        self.list.clear()
        if not computers:
            self.list.addItem(QListWidgetItem("В AD компьютеры не найдены."))
            return
        for comp in computers:
            name = comp.get("name", "")
            os_ = comp.get("os", "")
            item = QListWidgetItem(f"{name}    {os_}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(item)

    def _on_error(self, msg: str) -> None:
        self.list.clear()
        self.list.addItem(QListWidgetItem(f"Ошибка подключения к AD:\n{msg}"))
        InfoBar.error("AD недоступен", msg, parent=self,
                      position=InfoBarPosition.TOP, duration=6000)

    # ---------- выбор ----------
    def _check_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                it.setCheckState(state)

    def _filter(self, text: str) -> None:
        text = text.lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(text) and text not in it.text().lower())

    # ---------- импорт ----------
    def _import(self) -> None:
        selected = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if (it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and it.checkState() == Qt.CheckState.Checked):
                name = it.data(Qt.ItemDataRole.UserRole)
                sel = next((c for c in self.computers if c.get("name") == name), None)
                if sel:
                    selected.append(sel)
        if not selected:
            InfoBar.warning("Пусто", "Не выбрано ни одного компьютера.", parent=self,
                            position=InfoBarPosition.TOP, duration=3000)
            return
        self.progress.setVisible(True)
        self.progress.setValue(0)
        from app.services.import_service import ImportService
        svc = ImportService()
        stats = svc.import_ad_computers(
            selected,
            progress=lambda done, total: self.progress.setValue(int(done / max(total, 1) * 100)))
        InfoBar.success("Импорт завершён",
                        f"Создано: {stats['created']}, обновлено: {stats['updated']}, "
                        f"пропущено: {stats['skipped']}.",
                        parent=self, position=InfoBarPosition.TOP, duration=5000)
        self.imported.emit(stats)
        self.accept()
