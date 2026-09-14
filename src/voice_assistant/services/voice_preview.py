from __future__ import annotations

import asyncio
import importlib
import re

from google import genai
from google.genai import types

_CLIENTS: dict[str, genai.Client] = {}


def _client(api_key: str) -> genai.Client:
    if api_key not in _CLIENTS:
        _CLIENTS[api_key] = genai.Client(api_key=api_key)
    return _CLIENTS[api_key]


def _audio_bytes(response: types.GenerateContentResponse) -> bytes:
    for candidate in response.candidates or []:
        if candidate.content is None:
            continue
        for part in candidate.content.parts or []:
            if part.inline_data is not None and part.inline_data.data:
                return part.inline_data.data
    raise RuntimeError("Gemini returned no preview audio")


def _play_pcm(audio: bytes) -> None:
    sounddevice = importlib.import_module("sounddevice")
    with sounddevice.RawOutputStream(samplerate=24000, channels=1, dtype="int16") as stream:
        stream.write(audio)


async def preview_voice(
    api_key: str,
    voice: str,
    mood: str,
    speaking_style: str,
    *,
    text: str,
) -> None:
    client = _client(api_key)
    prompt = (
        f"Say the following line in a {mood or 'neutral'} mood and a "
        f"{speaking_style or 'natural'} speaking style. Say only the supplied line: {text}"
    )
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    await asyncio.to_thread(_play_pcm, _audio_bytes(response))


_TTS_TAG = re.compile(r"\[\[(.*?)\]\]")
_RESET_MOODS = {"", "normal", "default", "reset"}


def tts_segments(text: str) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    current_mood = ""
    for index, part in enumerate(_TTS_TAG.split(text)):
        if index % 2 == 1:
            mood = part.strip().lower()
            current_mood = "" if mood in _RESET_MOODS or mood.startswith("/") else mood
            continue
        if part.strip():
            segments.append((current_mood, part.strip()))
    return segments
