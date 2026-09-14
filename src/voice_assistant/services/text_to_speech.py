from __future__ import annotations

import logging
from pathlib import Path

from voice_assistant.domain.models import VoiceConfig, VoiceProviderConfig
from voice_assistant.services.piper_tts import speak_piper
from voice_assistant.services.voice_preview import preview_voice, tts_segments

_LOGGER = logging.getLogger(__name__)
_SUPPORTED_PROVIDERS = ("piper", "gemini")


class TtsConfigurationError(ValueError):
    pass


async def _speak_with_provider(
    provider_name: str,
    provider: VoiceProviderConfig,
    voice: VoiceConfig,
    text: str,
    *,
    base_directory: Path,
    voice_root: Path | None,
    api_key: str,
    output_device: str,
    output_latency: str,
    output_blocksize: int,
) -> None:
    for mood, segment in tts_segments(text):
        if provider_name == "piper":
            await speak_piper(
                provider,
                base_directory,
                segment,
                mood,
                voice_root=voice_root,
                output_device=output_device,
                output_latency=output_latency,
                output_blocksize=output_blocksize,
            )
        elif provider_name == "gemini":
            if not api_key:
                raise TtsConfigurationError("A Gemini API key is required for Gemini TTS")
            if not provider.voice:
                raise TtsConfigurationError("No Gemini voice is configured")
            await preview_voice(api_key, provider.voice, mood, voice.style, text=segment)
        else:
            raise TtsConfigurationError(f"Unsupported TTS provider: {provider_name}")


def provider_order(voice: VoiceConfig, fallback_order: tuple[str, ...]) -> tuple[str, ...]:
    requested = (voice.preferred_provider, *fallback_order)
    return tuple(
        name
        for index, name in enumerate(requested)
        if name in _SUPPORTED_PROVIDERS
        and name in voice.providers
        and name not in requested[:index]
    )


async def speak_text(
    voice: VoiceConfig,
    text: str,
    *,
    base_directory: Path,
    api_key: str = "",
    voice_root: Path | None = None,
    fallback_order: tuple[str, ...] = (),
    output_device: str = "",
    output_latency: str = "low",
    output_blocksize: int = 0,
) -> str:
    providers = provider_order(voice, fallback_order)
    if not providers:
        raise TtsConfigurationError(f"No {voice.preferred_provider} voice is configured")

    failures: list[str] = []
    for provider_name in providers:
        try:
            await _speak_with_provider(
                provider_name,
                voice.providers[provider_name],
                voice,
                text,
                base_directory=base_directory,
                voice_root=voice_root,
                api_key=api_key,
                output_device=output_device,
                output_latency=output_latency,
                output_blocksize=output_blocksize,
            )
        except Exception as exc:
            failures.append(f"{provider_name}: {exc}")
            if provider_name == providers[-1]:
                break
            _LOGGER.warning("TTS provider %s failed; trying fallback: %s", provider_name, exc)
        else:
            return provider_name
    raise RuntimeError("All configured TTS providers failed (" + "; ".join(failures) + ")")
