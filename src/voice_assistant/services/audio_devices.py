from __future__ import annotations

import importlib
from typing import Any


def output_devices() -> tuple[tuple[str, str], ...]:
    sounddevice = importlib.import_module("sounddevice")
    devices: list[tuple[str, str]] = []
    for index, device in enumerate(sounddevice.query_devices()):
        info: Any = device
        if int(info.get("max_output_channels", 0)) > 0:
            devices.append((str(index), f"{index}: {info['name']}"))
    return tuple(devices)


def output_device_value(value: str) -> int | str | None:
    if not value:
        return None
    return int(value) if value.isdigit() else value
