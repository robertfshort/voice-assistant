import asyncio
from pathlib import Path

from pytest import MonkeyPatch

from voice_assistant.domain.models import VoiceConfig, VoiceProviderConfig
from voice_assistant.services import text_to_speech
from voice_assistant.services.audio_devices import (
    convert_pcm16_channels,
    output_device_value,
    resample_pcm16,
)
from voice_assistant.services.piper_tts import resolve_voice_path


def test_output_device_value_supports_stable_device_indexes() -> None:
    assert output_device_value("") is None
    assert output_device_value("3") == 3
    assert output_device_value("Speakers") == "Speakers"
    assert output_device_value("default") is None
    assert output_device_value("Default") is None


def test_convert_pcm16_channels_duplicates_mono_to_stereo() -> None:
    source = b"\xe8\x03\xd0\x07"

    assert convert_pcm16_channels(source, 1, 2) == (b"\xe8\x03\xe8\x03\xd0\x07\xd0\x07")


def test_resample_pcm16_changes_frame_count_and_preserves_channels() -> None:
    source = b"\x00\x00\xe8\x03\xd0\x07\xb8\x0b"

    result = resample_pcm16(source, 2, 4, 2)

    assert len(result) == 16


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
        config: VoiceProviderConfig,
        base_directory: Path,
        text: str,
        mood: str = "",
        *,
        voice_root: Path | None = None,
        output_device: str = "",
        output_latency: str = "low",
        output_blocksize: int = 0,
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


def test_speak_text_falls_back_from_piper_to_gemini(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    calls: list[str] = []

    async def broken_piper(*args: object, **kwargs: object) -> None:
        calls.append("piper")
        raise FileNotFoundError("model missing")

    async def working_gemini(*args: object, **kwargs: object) -> None:
        calls.append("gemini")

    monkeypatch.setattr(text_to_speech, "speak_piper", broken_piper)
    monkeypatch.setattr(text_to_speech, "preview_voice", working_gemini)
    voice = VoiceConfig(
        preferred_provider="piper",
        providers={
            "piper": VoiceProviderConfig(model="missing.onnx"),
            "gemini": VoiceProviderConfig(voice="Kore"),
        },
    )

    used = asyncio.run(
        text_to_speech.speak_text(
            voice,
            "Hello.",
            base_directory=tmp_path,
            api_key="test-key",
            fallback_order=("gemini",),
        )
    )

    assert used == "gemini"
    assert calls == ["piper", "gemini"]
