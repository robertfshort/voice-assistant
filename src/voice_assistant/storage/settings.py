from __future__ import annotations

import sys
from pathlib import Path

import yaml
from platformdirs import user_config_path, user_data_path
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from voice_assistant.domain.errors import ConfigurationError


class StorageSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    campaign_root: Path | None = None
    portable_mode: bool = False


class ProviderSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation: str = "gemini"
    transcription: str = "gemini-live"
    speech: str = "gemini"


class SpeechSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    voice_root: Path | None = None
    fallback_order: tuple[str, ...] = ("piper", "gemini")
    output_device: str = ""
    output_latency: str = "low"
    output_blocksize: int = 0


class AppearanceSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    theme: str = "light"


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    storage: StorageSettings = Field(default_factory=StorageSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    speech: SpeechSettings = Field(default_factory=SpeechSettings)
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)


def default_settings_path() -> Path:
    return user_config_path("VoiceAssistant", "RobertShort") / "config.yaml"


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or default_settings_path()
    if not settings_path.exists():
        return AppSettings()
    try:
        raw = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        return AppSettings.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ConfigurationError(f"Unable to load settings from {settings_path}: {exc}") from exc


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    settings_path = path or default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json", exclude_none=True)
    temporary = settings_path.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    temporary.replace(settings_path)
    return settings_path


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def resolve_campaign_root(
    settings: StorageSettings,
    *,
    app_directory: Path | None = None,
    data_directory: Path | None = None,
) -> Path:
    if settings.campaign_root is not None and str(settings.campaign_root).strip():
        return settings.campaign_root.expanduser().resolve()
    if settings.portable_mode:
        return (app_directory or application_directory()).resolve() / "campaigns"
    base = data_directory or user_data_path("VoiceAssistant", "RobertShort")
    return base.resolve() / "campaigns"
