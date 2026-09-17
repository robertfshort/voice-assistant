from __future__ import annotations

import importlib
from typing import Any

import numpy as np


def output_devices() -> tuple[tuple[str, str], ...]:
    sounddevice = importlib.import_module("sounddevice")
    devices: list[tuple[str, str]] = []
    for index, device in enumerate(sounddevice.query_devices()):
        info: Any = device
        if int(info.get("max_output_channels", 0)) > 0:
            devices.append((str(index), f"{index}: {info['name']}"))
    return tuple(devices)


def output_device_value(value: str) -> int | str | None:
    if not value or value.lower() == "default":
        return None
    return int(value) if value.isdigit() else value


def output_sample_rate(device: str, source_rate: int, channels: int) -> int:
    if not device:
        return source_rate
    sounddevice = importlib.import_module("sounddevice")
    selected = output_device_value(device)
    try:
        sounddevice.check_output_settings(
            device=selected, samplerate=source_rate, channels=channels, dtype="int16"
        )
    except Exception:
        info: Any = sounddevice.query_devices(selected, "output")
        return int(round(float(info["default_samplerate"])))
    return source_rate


def convert_pcm16_channels(audio: bytes, source_channels: int, target_channels: int) -> bytes:
    if not audio or source_channels == target_channels:
        return audio
    frames = np.frombuffer(audio, dtype=np.int16).reshape(-1, source_channels)
    if target_channels == 1:
        converted = np.rint(frames.astype(np.float64).mean(axis=1)).astype(np.int16)
    elif source_channels == 1 and target_channels == 2:
        converted = np.repeat(frames, 2, axis=1)
    else:
        raise ValueError(f"Unsupported channel conversion: {source_channels} to {target_channels}")
    return converted.tobytes()


def resample_pcm16(audio: bytes, source_rate: int, target_rate: int, channels: int) -> bytes:
    if not audio or source_rate == target_rate:
        return audio
    frames = np.frombuffer(audio, dtype=np.int16).reshape(-1, channels)
    target_count = max(1, round(len(frames) * target_rate / source_rate))
    source_positions = np.arange(len(frames), dtype=np.float64)
    target_positions = np.linspace(0, len(frames) - 1, target_count)
    result = np.empty((target_count, channels), dtype=np.int16)
    for channel in range(channels):
        values = np.interp(target_positions, source_positions, frames[:, channel])
        result[:, channel] = np.clip(np.rint(values), -32768, 32767).astype(np.int16)
    return result.tobytes()
