from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import faster_whisper


class SessionTranscriber:
    def __init__(self, model: str = "base", compute_type: str = "int8") -> None:
        self.model_name = model
        self._compute_type = compute_type
        self._model: Any | None = None
        self._lock = threading.Lock()

    async def transcribe(self, audio_path: Path) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: Path) -> str:
        with self._lock:
            if self._model is None:
                self._model = faster_whisper.WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type=self._compute_type,
                    cpu_threads=0,
                )
        segments, _ = self._model.transcribe(str(audio_path))
        text = " ".join(segment.text.strip() for segment in segments)
        return text
