from __future__ import annotations

import asyncio
import importlib

from google import genai
from google.genai import types


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
    client = genai.Client(api_key=api_key)
    prompt = (
        f"Say the following line in a {mood or 'neutral'} mood and a "
        f"{speaking_style or 'natural'} speaking style. Say only the supplied line: {text}"
    )
    try:
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
    finally:
        await client.aio.aclose()
