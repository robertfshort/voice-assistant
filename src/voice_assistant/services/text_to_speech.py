from __future__ import annotations

from pathlib import Path

from voice_assistant.domain.models import VoiceConfig
from voice_assistant.services.piper_tts import speak_piper
from voice_assistant.services.voice_preview import preview_voice, tts_segments


class TtsConfigurationError(ValueError):
    pass


async def speak_text(
    voice: VoiceConfig,
    text: str,
    *,
    base_directory: Path,
    api_key: str = "",
) -> None:
    provider_name = voice.preferred_provider
    provider = voice.providers.get(provider_name)
    if provider is None:
        raise TtsConfigurationError(f"No {provider_name} voice is configured")

    for mood, segment in tts_segments(text):
        if provider_name == "piper":
            await speak_piper(provider, base_directory, segment, mood)
        elif provider_name == "gemini":
            if not api_key:
                raise TtsConfigurationError("A Gemini API key is required for Gemini TTS")
            if not provider.voice:
                raise TtsConfigurationError("No Gemini voice is configured")
            await preview_voice(api_key, provider.voice, mood, voice.style, text=segment)
        else:
            raise TtsConfigurationError(f"Unsupported TTS provider: {provider_name}")
