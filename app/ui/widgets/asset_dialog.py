# -*- coding: utf-8 -*-
"""Карточка актива: диалог с вкладками Основное / Железо / История.

CRUD актива, обновление железа из WMI («Обновить железо»), таймлайн событий.
"""
import json
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QStackedWidget,
)
from qfluentwidgets import (
    PushButton, PrimaryPushButton, LineEdit, ComboBox, TextEdit, FluentIcon,
    InfoBar, InfoBarPosition, SegmentedWidget, BodyLabel, SubtitleLabel,
    CardWidget, IconWidget, SpinBox,
)

from app.models.database import get_db, ASSET_TYPES, ASSET_STATUSES


class AssetDialog(QDialog):
    """Карточка компьютера/актива. Открытие по двойному клику в таблице."""

    saved = pyqtSignal(int)    # id актива
    deleted = pyqtSignal(int)  # id удалённого актива

    def __init__(self, asset_id: int | None = None, default_type: str = "computer",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.db = get_db()
        self.asset_id = asset_id
        self.is_new = asset_id is None
        self.asset = self.db.get_asset(asset_id) if asset_id else {"type": default_type}

        self.setWindowTitle("Карточка актива — AscoldIT" if not self.is_new
                            else "Новый актив — AscoldIT")
        self.resize(720, 620)
        self.setStyleSheet("QDialog { font-family: 'Segoe UI Variable', 'Segoe UI'; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # --- заголовок + переключатель вкладок ---
        header = QHBoxLayout()
        self.icon = IconWidget(FluentIcon.PC)
        self.icon.setFixedSize(28, 28)
        self.title = SubtitleLabel(self.asset.get("name") or "Новый актив")
        header.addWidget(self.icon)
        header.addWidget(self.title)
        header.addStretch(1)
        self.segmented = SegmentedWidget()
        for rid, text in (("main", "Основное"), ("hw", "Железо"), ("hist", "История")):
            self.segmented.addItem(rid, text)
        self.segmented.setCurrentItem("main")
        self.segmented.items["main"].clicked.connect(lambda: self._switch("main"))
        self.segmented.items["hw"].clicked.connect(lambda: self._switch("hw"))
        self.segmented.items["hist"].clicked.connect(lambda: self._switch("hist"))
        header.addWidget(self.segmented)
        root.addLayout(header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_main_tab())
        self.stack.addWidget(self._build_hw_tab())
        self.stack.addWidget(self._build_history_tab())

        # --- кнопки ---
        btns = QHBoxLayout()
        self.btnDelete = PushButton(FluentIcon.DELETE, "Удалить")
        self.btnDelete.setVisible(not self.is_new)
        self.btnDelete.clicked.connect(self._delete)
        btnCancel = PushButton(FluentIcon.CLOSE, "Отмена")
        btnCancel.clicked.connect(self.reject)
        btnSave = PrimaryPushButton(FluentIcon.SAVE, "Сохранить")
        btnSave.clicked.connect(self._save)
        btns.addWidget(self.btnDelete)
        btns.addStretch(1)
        btns.addWidget(btnCancel)
        btns.addWidget(btnSave)
        root.addLayout(btns)

    def _switch(self, rid: str) -> None:
        self.stack.setCurrentIndex({"main": 0, "hw": 1, "hist": 2}[rid])

    # ---------- вкладка «Основное» ----------
    def _build_main_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(6, 12, 6, 6)
        form.setSpacing(10)
        a = self.asset

        self.edName = LineEdit(None)
        self.edName.setText(str(a.get("name", "")))
        self.edName.setPlaceholderText("Например: PC-BUH-01")
        self.cbType = ComboBox()
        for code, label in ASSET_TYPES.items():
            self.cbType.addItem(label, userData=code)
        idx = self.cbType.findData(a.get("type", "computer"))
        self.cbType.setCurrentIndex(max(idx, 0))
        self.cbStatus = ComboBox()
        self.cbStatus.addItems(ASSET_STATUSES)
        st = str(a.get("status", ASSET_STATUSES[0]))
        sidx = self.cbStatus.findText(st)
        self.cbStatus.setCurrentIndex(max(sidx, 0))
        self.edLocation = LineEdit(None)
        self.edLocation.setText(str(a.get("location", "")))
        self.edLocation.setPlaceholderText("Корпус 1 / Этаж 2 / Кабинет 205")

        # пользователь: ФИО из справочника
        self.cbUser = ComboBox()
        self.cbUser.addItem("— не назначен —", userData=None)
        users = self.db.get_users()
        uid = a.get("user_id")
        for u in users:
            dep = f" ({u['department']})" if u.get("department") else ""
            self.cbUser.addItem(f"{u['fio']}{dep}", userData=u["id"])
        uidx = self.cbUser.findData(uid)
        self.cbUser.setCurrentIndex(max(uidx, 0))

        self.edSerial = LineEdit(None)
        self.edSerial.setText(str(a.get("serial", "")))
        self.edManufacturer = LineEdit(None)
        self.edManufacturer.setText(str(a.get("manufacturer", "")))
        self.edModel = LineEdit(None)
        self.edModel.setText(str(a.get("model", "")))
        self.edInventory = LineEdit(None)
        self.edInventory.setText(str(a.get("inventory_no", "")))
        self.edIp = LineEdit(None)
        self.edIp.setText(str(a.get("ip", "")))
        self.edIp.setPlaceholderText("10.0.0.1")
        self.edMac = LineEdit(None)
        self.edMac.setText(str(a.get("mac", "")))
        self.edMac.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        self.edNotes = TextEdit()
        self.edNotes.setText(str(a.get("notes", "")))
        self.edNotes.setMaximumHeight(90)

        form.addRow("Имя актива:", self.edName)
        form.addRow("Тип:", self.cbType)
        form.addRow("Статус:", self.cbStatus)
        form.addRow("Местоположение:", self.edLocation)
        form.addRow("Пользователь:", self.cbUser)
        form.addRow("Серийный номер:", self.edSerial)
        form.addRow("Производитель:", self.edManufacturer)
        form.addRow("Модель:", self.edModel)
        form.addRow("Инвентарный №:", self.edInventory)
        form.addRow("IP-адрес:", self.edIp)
        form.addRow("MAC-адрес:", self.edMac)
        form.addRow("Примечания:", self.edNotes)
        return w

    # ---------- вкладка «Железо» ----------
    def _build_hw_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(6, 12, 6, 6)
        outer.setSpacing(10)

        topbar = QHBoxLayout()
        self.btnWmi = PrimaryPushButton(FluentIcon.SYNC, "Обновить железо из WMI")
        self.btnWmi.clicked.connect(self._update_from_wmi)
        hint = BodyLabel("Запрос к машине по WMI (нужны права администратора домена)")
        hint.setTextColor(Qt.GlobalColor.gray)
        topbar.addWidget(self.btnWmi)
        topbar.addWidget(hint)
        topbar.addStretch(1)
        outer.addLayout(topbar)

        hw = self.db.get_hardware(self.asset_id) if self.asset_id else {}
        hw = hw or {}
        self.hwEdits: dict[str, LineEdit] = {}
        form = QFormLayout()
        form.setSpacing(10)
        for key, label in (("cpu", "Процессор"), ("ram_total", "ОЗУ (объём)"),
                           ("ram_type", "Тип ОЗУ"), ("disk_type", "Диск (тип)"),
                           ("disk_size", "Диск (объём)"), ("gpu", "Видеокарта"),
                           ("os_version", "ОС"), ("bios_serial", "Серийный № BIOS")):
            ed = LineEdit(None)
            ed.setText(str(hw.get(key, "")))
            self.hwEdits[key] = ed
            form.addRow(f"{label}:", ed)
        self.lblLastSeen = BodyLabel(f"Последние данные: {hw.get('last_seen') or 'нет'}")
        outer.addLayout(form)
        outer.addWidget(self.lblLastSeen)
        outer.addStretch(1)
        return w

    # ---------- вкладка «История» ----------
    def _build_history_tab(self) -> QWidget:
        from qfluentwidgets import ScrollArea
        area = ScrollArea()
        area.setWidgetResizable(True)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(6, 12, 6, 6)
        lay.setSpacing(8)
        events = self.db.get_events(self.asset_id, limit=100) if self.asset_id else []
        if not events:
            lay.addWidget(BodyLabel("Событий пока нет — журнал заполняется при создании, "
                                    "изменении и обновлении актива."))
        action_labels = {
            "create": ("Создание актива", FluentIcon.ADD),
            "update": ("Изменение карточки", FluentIcon.EDIT),
            "delete": ("Удаление", FluentIcon.DELETE),
            "hardware_update": ("Обновление железа", FluentIcon.SYNC),
            "import": ("Импорт", FluentIcon.DOWN),
            "ad_import": ("Импорт из AD", FluentIcon.GLOBE),
        }
        for ev in events:
            card = CardWidget()
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            icon = IconWidget(action_labels.get(ev["action"], (ev["action"], FluentIcon.INFO))[1])
            icon.setFixedSize(18, 18)
            text = BodyLabel(f"{action_labels.get(ev['action'], (ev['action'],))[0]} · {ev['ts']} · {ev['user']}")
            det = ev.get("details", {})
            short = ", ".join(f"{k}: {v}" for k, v in list(det.items())[:4]) if det else ""
            if short:
                text.setToolTip(json.dumps(det, ensure_ascii=False, indent=1))
            cl.addWidget(icon)
            cl.addWidget(text)
            cl.addStretch(1)
            lay.addWidget(card)
        lay.addStretch(1)
        area.setWidget(container)
        return area

    # ---------- действия ----------
    def collect_data(self) -> dict:
        return {
            "name": self.edName.text().strip(),
            "type": self.cbType.currentData(),
            "status": self.cbStatus.currentText(),
            "location": self.edLocation.text().strip(),
            "user_id": self.cbUser.currentData(),
            "serial": self.edSerial.text().strip(),
            "manufacturer": self.edManufacturer.text().strip(),
            "model": self.edModel.text().strip(),
            "inventory_no": self.edInventory.text().strip(),
            "ip": self.edIp.text().strip(),
            "mac": self.edMac.text().strip(),
            "notes": self.edNotes.toPlainText().strip(),
        }

    def _save(self) -> None:
        data = self.collect_data()
        if not data["name"]:
            InfoBar.warning("Проверьте данные", "Поле «Имя актива» обязательно для заполнения.",
                            parent=self, position=InfoBarPosition.TOP, duration=4000)
            return
        if self.is_new:
            self.asset_id = self.db.add_asset(data)
            self.is_new = False
        else:
            self.db.update_asset(self.asset_id, data)
        hw_data = {k: ed.text().strip() for k, ed in self.hwEdits.items()}
        if any(hw_data.values()):
            self.db.upsert_hardware(self.asset_id, hw_data)
        InfoBar.success("Сохранено", f"Актив «{data['name']}» сохранён, запись добавлена в события.",
                        parent=self, position=InfoBarPosition.TOP, duration=3000)
        self.saved.emit(self.asset_id)
        self.accept()

    def _delete(self) -> None:
        from qfluentwidgets import MessageBox
        box = MessageBox("Удалить актив?",
                         f"Актив «{self.edName.text()}» будет удалён вместе с данными о железе.\n"
                         "История событий сохранится.", self)
        if box.exec():
            self.db.delete_asset(self.asset_id)
            self.deleted.emit(self.asset_id)
            self.accept()

    def _update_from_wmi(self) -> None:
        hostname = self.edName.text().strip()
        if not hostname:
            InfoBar.warning("Нет имени", "Укажите имя компьютера перед запросом WMI.",
                            parent=self, position=InfoBarPosition.TOP, duration=3000)
            return
        self.btnWmi.setEnabled(False)
        self.btnWmi.setText("Запрос WMI…")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        try:
            from app.services.wmi_service import get_hardware_info, WMIServiceError
            info = get_hardware_info(hostname)
            for k, ed in self.hwEdits.items():
                if info.get(k):
                    ed.setText(str(info[k]))
            self.lblLastSeen.setText(f"Последние данные: {info.get('last_seen', '')}")
            if self.asset_id and not self.is_new:
                self.db.upsert_hardware(self.asset_id, info)
            InfoBar.success("WMI", "Информация о железе обновлена.",
                            parent=self, position=InfoBarPosition.TOP, duration=3000)
        except Exception as e:
            InfoBar.error("WMI недоступен", str(e), parent=self,
                          position=InfoBarPosition.TOP, duration=6000)
        finally:
            self.btnWmi.setEnabled(True)
            self.btnWmi.setText("Обновить железо из WMI")
