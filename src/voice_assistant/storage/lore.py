from __future__ import annotations

from pathlib import Path, PurePosixPath

from voice_assistant.domain.errors import CampaignError

_ALLOWED_SUFFIXES = {".md", ".txt"}


def lore_path(campaign_directory: Path, lore_id: str) -> Path:
    relative = PurePosixPath(lore_id)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or relative.suffix.lower() not in _ALLOWED_SUFFIXES
    ):
        raise CampaignError(f"Invalid lore file name: {lore_id!r}")
    root = (campaign_directory / "lore").resolve()
    destination = (root / Path(*relative.parts)).resolve()
    if not destination.is_relative_to(root):
        raise CampaignError(f"Lore file is outside the campaign lore directory: {lore_id!r}")
    return destination


def save_lore(campaign_directory: Path, lore_id: str, content: str) -> Path:
    destination = lore_path(campaign_directory, lore_id)
    if not destination.exists():
        raise CampaignError(f"Lore file does not exist: {destination}")
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(destination)
    except OSError as exc:
        raise CampaignError(f"Unable to save lore file {destination}: {exc}") from exc
    return destination
