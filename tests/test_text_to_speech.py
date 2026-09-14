import asyncio
from pathlib import Path

from pytest import MonkeyPatch

from voice_assistant.domain.models import VoiceConfig, VoiceProviderConfig
from voice_assistant.services import text_to_speech
from voice_assistant.services.piper_tts import resolve_voice_path


def test_relative_piper_model_resolves_from_campaign_directory(tmp_path: Path) -> None:
    assert (
        resolve_voice_path("voices/mara.onnx", tmp_path)
        == (tmp_path / "voices" / "mara.onnx").resolve()
    )


def test_speak_text_routes_tagged_segments_to_piper(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_speak(
        config: VoiceProviderConfig, base_directory: Path, text: str, mood: str = ""
    ) -> None:
        assert config.model == "voices/mara.onnx"
        assert base_directory == tmp_path
        calls.append((mood, text))

    monkeypatch.setattr(text_to_speech, "speak_piper", fake_speak)
    voice = VoiceConfig(
        preferred_provider="piper",
        providers={"piper": VoiceProviderConfig(model="voices/mara.onnx")},
    )

    asyncio.run(
        text_to_speech.speak_text(
            voice,
            "Hello. [[whisper]] Keep this quiet.",
            base_directory=tmp_path,
        )
    )

    assert calls == [("", "Hello."), ("whisper", "Keep this quiet.")]
