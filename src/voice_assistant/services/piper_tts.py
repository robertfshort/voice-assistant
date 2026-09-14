from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Any

from voice_assistant.domain.models import VoiceProviderConfig
from voice_assistant.services.audio_devices import output_device_value
from voice_assistant.storage.voices import resolve_registered_voice

_VOICES: dict[tuple[Path, Path | None], Any] = {}
_MOOD_OVERRIDES = {
    "whisper": (1.15, 0.45),
    "nervously": (0.92, 0.8),
    "shout": (0.85, 0.75),
}


def resolve_voice_path(path: str, base_directory: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base_directory / candidate
    return candidate.resolve()


def _load_voice(model: Path, config: Path | None) -> Any:
    key = (model, config)
    if key not in _VOICES:
        piper = importlib.import_module("piper")
        _VOICES[key] = piper.PiperVoice.load(model, config_path=config)
    return _VOICES[key]


def _synthesize(
    config: VoiceProviderConfig,
    base_directory: Path,
    voice_root: Path | None,
    text: str,
    mood: str,
    output_device: str,
    output_latency: str,
    output_blocksize: int,
) -> None:
    registered = resolve_registered_voice(config.voice, voice_root)
    if registered is not None:
        model, config_path = registered
    elif config.model:
        model = resolve_voice_path(config.model, base_directory)
        config_path = resolve_voice_path(config.config, base_directory) if config.config else None
    else:
        name = f" named {config.voice!r}" if config.voice else ""
        raise ValueError(f"No Piper model is configured{name}")
    if not model.is_file():
        raise FileNotFoundError(f"Piper model not found: {model}")
    if config_path is not None and not config_path.is_file():
        raise FileNotFoundError(f"Piper config not found: {config_path}")

    piper = importlib.import_module("piper")
    length_scale, noise_scale = _MOOD_OVERRIDES.get(
        mood.lower(), (config.length_scale, config.noise_scale)
    )
    synthesis = piper.SynthesisConfig(
        speaker_id=config.speaker_id,
        length_scale=length_scale,
        noise_scale=noise_scale,
        noise_w_scale=config.noise_w,
    )
    sounddevice = importlib.import_module("sounddevice")
    voice = _load_voice(model, config_path)
    stream = None
    try:
        for chunk in voice.synthesize(text, syn_config=synthesis):
            if stream is None:
                stream = sounddevice.RawOutputStream(
                    samplerate=chunk.sample_rate,
                    channels=chunk.sample_channels,
                    dtype="int16",
                    device=output_device_value(output_device),
                    latency=output_latency,
                    blocksize=output_blocksize,
                )
                stream.start()
            stream.write(chunk.audio_int16_bytes)
    finally:
        if stream is not None:
            stream.stop()
            stream.close()


async def speak_piper(
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
    await asyncio.to_thread(
        _synthesize,
        config,
        base_directory,
        voice_root,
        text,
        mood,
        output_device,
        output_latency,
        output_blocksize,
    )
