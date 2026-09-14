from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from voice_assistant.domain.errors import ConfigurationError


class PiperVoiceAsset(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    config: str = ""


class VoiceRegistry(BaseModel):
    model_config = ConfigDict(frozen=True)

    piper: dict[str, PiperVoiceAsset] = Field(default_factory=dict)


def load_voice_registry(root: Path | None) -> VoiceRegistry:
    if root is None:
        return VoiceRegistry()
    path = root / "voices.yaml"
    if not path.exists():
        return VoiceRegistry()
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return VoiceRegistry.model_validate(value)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ConfigurationError(f"Unable to load voice registry from {path}: {exc}") from exc


def resolve_registered_voice(name: str, root: Path | None) -> tuple[Path, Path | None] | None:
    if not name or root is None:
        return None
    asset = load_voice_registry(root).piper.get(name)
    if asset is None:
        return None
    model = (root / asset.model).resolve()
    config = (root / asset.config).resolve() if asset.config else None
    return model, config
