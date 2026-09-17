import asyncio
from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch

from voice_assistant.services import session_transcription as session_transcription_module
from voice_assistant.services.session_transcription import SessionTranscriber


class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def transcribe(self, audio_path: str) -> tuple[list[_FakeSegment], object]:
        return ([_FakeSegment("Hello "), _FakeSegment("world")], SimpleNamespace())


def test_session_transcriber_combines_segment_text(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    fake_faster_whisper = SimpleNamespace(WhisperModel=_FakeModel)
    monkeypatch.setattr(session_transcription_module, "faster_whisper", fake_faster_whisper)

    transcriber = SessionTranscriber()
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("", encoding="utf-8")

    text = asyncio.run(transcriber.transcribe(audio_path))

    assert text == "Hello world"
