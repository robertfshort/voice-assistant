from __future__ import annotations

import re
import shutil
from contextlib import suppress
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from voice_assistant.domain.errors import ConfigurationError

_VOICE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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


def _save_registry(root: Path, registry: VoiceRegistry) -> None:
    root.mkdir(parents=True, exist_ok=True)
    data = registry.model_dump(mode="json")
    registry_path = root / "voices.yaml"
    temporary = root / "voices.yaml.tmp"
    temporary.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n")
    temporary.replace(registry_path)


def import_piper_voice(root: Path, name: str, model: Path, config: Path | None) -> None:
    if not _VOICE_NAME.fullmatch(name):
        raise ConfigurationError("Voice name must use lowercase letters, numbers, and hyphens")
    if model.suffix.lower() != ".onnx" or not model.is_file():
        raise ConfigurationError(f"Piper model does not exist or is not an ONNX file: {model}")
    if config is not None and (config.suffix.lower() != ".json" or not config.is_file()):
        raise ConfigurationError(f"Piper config does not exist or is not JSON: {config}")
    registry = load_voice_registry(root)
    if name in registry.piper:
        raise ConfigurationError(f"A voice named {name!r} is already registered")

    target = root / "piper" / name
    if target.exists():
        raise ConfigurationError(f"Voice asset directory already exists: {target}")
    try:
        target.mkdir(parents=True)
    except OSError as exc:
        raise ConfigurationError(f"Unable to create voice asset directory: {exc}") from exc
    model_target = target / model.name
    config_target = target / config.name if config is not None else None
    try:
        shutil.copy2(model, model_target)
        if config is not None and config_target is not None:
            shutil.copy2(config, config_target)
        voices = dict(registry.piper)
        voices[name] = PiperVoiceAsset(
            model=model_target.relative_to(root).as_posix(),
            config=config_target.relative_to(root).as_posix() if config_target else "",
        )
        _save_registry(root, VoiceRegistry(piper=voices))
    except OSError as exc:
        shutil.rmtree(target, ignore_errors=True)
        (root / "voices.yaml.tmp").unlink(missing_ok=True)
        raise ConfigurationError(f"Unable to import Piper voice: {exc}") from exc


def replace_piper_voice(root: Path, name: str, model: Path, config: Path | None) -> None:
    if model.suffix.lower() != ".onnx" or not model.is_file():
        raise ConfigurationError(f"Piper model does not exist or is not an ONNX file: {model}")
    if config is not None and (config.suffix.lower() != ".json" or not config.is_file()):
        raise ConfigurationError(f"Piper config does not exist or is not JSON: {config}")
    registry = load_voice_registry(root)
    if name not in registry.piper:
        raise ConfigurationError(f"No registered Piper voice named {name!r}")
    target = root / "piper" / name
    staging = target.parent / f".{name}.update"
    backup = target.parent / f".{name}.backup"
    if staging.exists() or backup.exists():
        raise ConfigurationError(f"A previous update for {name!r} requires manual cleanup")
    staging.mkdir(parents=True)
    model_target = staging / model.name
    config_target = staging / config.name if config is not None else None
    replaced = False
    try:
        shutil.copy2(model, model_target)
        if config is not None and config_target is not None:
            shutil.copy2(config, config_target)
        target.rename(backup)
        staging.rename(target)
        replaced = True
        voices = dict(registry.piper)
        voices[name] = PiperVoiceAsset(
            model=(target / model.name).relative_to(root).as_posix(),
            config=(target / config.name).relative_to(root).as_posix() if config else "",
        )
        _save_registry(root, VoiceRegistry(piper=voices))
    except OSError as exc:
        if replaced:
            with suppress(OSError):
                target.rename(staging)
                backup.rename(target)
        shutil.rmtree(staging, ignore_errors=True)
        raise ConfigurationError(f"Unable to update Piper voice {name!r}: {exc}") from exc
    with suppress(OSError):
        shutil.rmtree(backup)


def remove_piper_voice(root: Path, name: str) -> None:
    registry = load_voice_registry(root)
    if name not in registry.piper:
        raise ConfigurationError(f"No registered Piper voice named {name!r}")
    resolved = resolve_registered_voice(name, root)
    if resolved is None:
        raise ConfigurationError(f"Unable to resolve Piper voice {name!r}")
    voices = dict(registry.piper)
    del voices[name]
    try:
        _save_registry(root, VoiceRegistry(piper=voices))
        model, config = resolved
        model.unlink(missing_ok=True)
        if config is not None:
            config.unlink(missing_ok=True)
        if model.parent != root.resolve():
            with suppress(OSError):
                model.parent.rmdir()
    except OSError as exc:
        raise ConfigurationError(f"Unable to remove Piper voice {name!r}: {exc}") from exc


def resolve_registered_voice(name: str, root: Path | None) -> tuple[Path, Path | None] | None:
    if not name or root is None:
        return None
    asset = load_voice_registry(root).piper.get(name)
    if asset is None:
        return None
    resolved_root = root.resolve()
    model = (resolved_root / asset.model).resolve()
    config = (resolved_root / asset.config).resolve() if asset.config else None
    if not model.is_relative_to(resolved_root) or (
        config is not None and not config.is_relative_to(resolved_root)
    ):
        raise ConfigurationError(f"Registered voice {name!r} points outside the voice folder")
    return model, config
