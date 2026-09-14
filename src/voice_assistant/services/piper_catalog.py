from __future__ import annotations

import asyncio
import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from voice_assistant.storage.voices import import_piper_voice

_CATALOG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
_FILE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{}"


@dataclass(frozen=True)
class PiperCatalogVoice:
    key: str
    name: str
    language: str
    country: str
    quality: str
    speakers: int
    size_bytes: int
    model_size: int
    config_size: int
    model_path: str
    model_digest: str
    config_path: str
    config_digest: str

    @property
    def size_mib(self) -> float:
        return self.size_bytes / (1024 * 1024)


def parse_catalog(data: dict[str, Any]) -> tuple[PiperCatalogVoice, ...]:
    voices: list[PiperCatalogVoice] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        files = value.get("files", {})
        language = value.get("language", {})
        if not isinstance(files, dict) or not isinstance(language, dict):
            continue
        model_path = next((path for path in files if path.endswith(".onnx")), "")
        config_path = next((path for path in files if path.endswith(".onnx.json")), "")
        if not model_path or not config_path:
            continue
        model = files[model_path]
        config = files[config_path]
        if not isinstance(model, dict) or not isinstance(config, dict):
            continue
        voices.append(
            PiperCatalogVoice(
                key=str(value.get("key", key)),
                name=str(value.get("name", key)),
                language=str(language.get("name_english", language.get("code", "Unknown"))),
                country=str(language.get("country_english", "")),
                quality=str(value.get("quality", "unknown")),
                speakers=int(value.get("num_speakers", 1)),
                size_bytes=int(model.get("size_bytes", 0)) + int(config.get("size_bytes", 0)),
                model_size=int(model.get("size_bytes", 0)),
                config_size=int(config.get("size_bytes", 0)),
                model_path=model_path,
                model_digest=str(model.get("md5_digest", "")),
                config_path=config_path,
                config_digest=str(config.get("md5_digest", "")),
            )
        )
    return tuple(sorted(voices, key=lambda voice: voice.key))


async def fetch_piper_catalog() -> tuple[PiperCatalogVoice, ...]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(_CATALOG_URL)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Piper voice catalog did not contain an object")
    return parse_catalog(data)


def _download_file(
    client: httpx.Client,
    relative_path: str,
    target: Path,
    digest: str,
    expected_size: int,
) -> None:
    url = _FILE_URL.format(quote(relative_path, safe="/"))
    checksum = hashlib.md5(usedforsecurity=False)
    downloaded = 0
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with target.open("wb") as output:
            for chunk in response.iter_bytes():
                downloaded += len(chunk)
                if expected_size and downloaded > expected_size:
                    raise ValueError(f"Download exceeded catalog size for {relative_path}")
                output.write(chunk)
                checksum.update(chunk)
    if expected_size and downloaded != expected_size:
        target.unlink(missing_ok=True)
        raise ValueError(f"Download size mismatch for {relative_path}")
    if digest and checksum.hexdigest() != digest:
        target.unlink(missing_ok=True)
        raise ValueError(f"Checksum mismatch for {relative_path}")


def _download_voice(voice: PiperCatalogVoice, root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="piper-voice-") as temporary:
        directory = Path(temporary)
        model = directory / Path(voice.model_path).name
        config = directory / Path(voice.config_path).name
        with httpx.Client(follow_redirects=True, timeout=120) as client:
            _download_file(client, voice.model_path, model, voice.model_digest, voice.model_size)
            _download_file(
                client, voice.config_path, config, voice.config_digest, voice.config_size
            )
        import_piper_voice(root, voice.key.lower().replace("_", "-"), model, config)


async def download_piper_voice(voice: PiperCatalogVoice, root: Path) -> str:
    await asyncio.to_thread(_download_voice, voice, root)
    return voice.key.lower().replace("_", "-")
