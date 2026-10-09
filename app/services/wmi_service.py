# -*- coding: utf-8 -*-
"""Сервис получения информации о железе через WMI (pywin32 / wmi).

Метод get_hardware_info(hostname) возвращает dict с полями cpu, ram_total,
ram_type, disk_type, disk_size, gpu, os_version, bios_serial.
Локальная машина: hostname='' или 'localhost'. Удалённые машины — по сети (WMI).
"""
from datetime import datetime


class WMIServiceError(Exception):
    """Ошибка WMI-запроса."""


def _bytes_to_gb(n: float) -> str:
    return f"{n / (1024 ** 3):.0f} ГБ" if n else ""


def get_hardware_info(hostname: str = "") -> dict:
    """Собрать информацию о железе через WMI.

    :param hostname: имя компьютера (пусто => локальная машина)
    :return: dict(cpu, ram_total, ram_type, disk_type, disk_size, gpu,
                  os_version, bios_serial, last_seen)
    """
    try:
        import wmi as _wmi  # pip install wmi (зависит от pywin32)
    except ImportError:
        raise WMIServiceError("Модуль wmi/pywin32 недоступен (работает только в Windows).")

    target = hostname.strip() or "localhost"
    try:
        if target.lower() in ("localhost", "127.0.0.1", "."):
            c = _wmi.WMI()
        else:
            # подключение к удалённой машине в домене от имени текущего пользователя
            c = _wmi.WMI(f"{target}\\", authenticationLevel=5, impersonationLevel=3)
    except Exception as e:
        raise WMIServiceError(f"Не удалось подключиться по WMI к «{target}»: {e}") from e

    info: dict[str, str] = {}
    try:
        # Процессор
        cpus = c.Win32_Processor()
        if cpus:
            cpu = cpus[0]
            cores = getattr(cpu, "NumberOfCores", 0) or 0
            threads = getattr(cpu, "NumberOfLogicalProcessors", 0) or 0
            info["cpu"] = f"{cpu.Name.strip()} ({cores} ядер / {threads} потоков)"

        # Оперативная память
        modules = c.Win32_PhysicalMemory()
        if modules:
            total = sum(int(m.Capacity) for m in modules)
            speeds = {f"{m.Speed} МГц" for m in modules if getattr(m, "Speed", None)}
            kinds = set()
            for m in modules:
                smbt = getattr(m, "SMBIOSMemoryType", None)
                typ = getattr(m, "MemoryType", None)
                if smbt == 34:
                    kinds.add("DDR5")
                elif smbt == 26 or typ == 20:
                    kinds.add("DDR4")
                elif smbt == 24 or typ == 18:
                    kinds.add("DDR3")
                elif m.ConfiguredClockSpeed:
                    kinds.add("DDR")
            info["ram_total"] = _bytes_to_gb(total)
            info["ram_type"] = ", ".join(sorted(kinds)) + (f", {', '.join(sorted(speeds))}" if speeds else "")

        # Диски (физические): SSD/HDD и объём
        disks = c.Win32_DiskDrive()
        if disks:
            total_size = sum(int(d.Size) for d in disks if getattr(d, "Size", None))
            media = " ".join((getattr(d, "MediaType", "") or "").lower() for d in disks)
            model = disks[0].Model.strip() if disks else ""
            if "ssd" in media or "solid" in media:
                dtype = "SSD"
            elif "hdd" in media or "fixed hard disk" in media:
                dtype = "HDD"
            else:
                dtype = "SSD/HDD"
            info["disk_type"] = f"{dtype} ({model})" if model else dtype
            info["disk_size"] = _bytes_to_gb(total_size)

        # Видеокарта
        gpus = c.Win32_VideoController()
        if gpus:
            info["gpu"] = "; ".join(g.Name.strip() for g in gpus[:2])

        # ОС
        oss = c.Win32_OperatingSystem()
        if oss:
            info["os_version"] = f"{oss.Caption.strip()} build {oss.BuildNumber}"

        # BIOS / серийный номер
        bios = c.Win32_BIOS()
        if bios:
            info["bios_serial"] = bios.SerialNumber.strip()
            manufacturer = bios.Manufacturer.strip()
            if manufacturer and not info.get("manufacturer"):
                pass  # производитель машины можно добавить при необходимости

        info["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        raise WMIServiceError(f"Ошибка WMI-запроса к «{target}»: {e}") from e

    if len(info) <= 1:
        raise WMIServiceError(f"WMI не вернул данных по машине «{target}».")
    return info


def is_wmi_available() -> bool:
    """Доступен ли WMI (Windows + pywin32 + wmi)."""
    try:
        import platform
        if platform.system() != "Windows":
            return False
        import wmi  # noqa: F401
        return True
    except Exception:
        return False
