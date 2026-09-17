from __future__ import annotations

import importlib
import queue
import wave
from pathlib import Path
from typing import Any


class SessionAudioRecorder:
    def __init__(self, *, sample_rate: int = 16000, input_device: str = "") -> None:
        self._sample_rate = sample_rate
        self._input_device = input_device
        self._frames: queue.Queue[bytes] = queue.Queue()
        self._stream: Any | None = None
        self._sounddevice: Any | None = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None and not self._stream.stopped

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Recording already in progress")
        self._sounddevice = importlib.import_module("sounddevice")
        device: int | str | None = (
            int(self._input_device) if self._input_device.isdigit() else self._input_device or None
        )
        self._frames = queue.Queue()
        self._stream = self._sounddevice.RawInputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            device=device,
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata: Any, *args: Any) -> None:
        data: bytes = indata.tobytes() if hasattr(indata, "tobytes") else bytes(indata)
        self._frames.put(data)

    def stop(self, output_path: Path) -> None:
        if self._stream is None:
            raise RuntimeError("Recording not in progress")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self._sample_rate)
            while not self._frames.empty():
                wav.writeframes(self._frames.get())
