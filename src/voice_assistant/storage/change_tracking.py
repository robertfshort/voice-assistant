from __future__ import annotations

import datetime
import shutil
from pathlib import Path
from typing import Any

import yaml

from voice_assistant.domain.errors import CampaignError


def _timestamp() -> str:
    return datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d-%H%M%S-%f")


def _changelog_path(campaign_directory: Path) -> Path:
    return campaign_directory / "changelog.yaml"


def _load_changelog(campaign_directory: Path) -> list[dict[str, Any]]:
    path = _changelog_path(campaign_directory)
    if not path.exists():
        return []
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        raise CampaignError(f"Invalid changelog in {path}: {exc}") from exc
    if not isinstance(value, list):
        raise CampaignError(f"Expected a YAML list in {path}")
    return value


def _save_changelog(campaign_directory: Path, entries: list[dict[str, Any]]) -> None:
    path = _changelog_path(campaign_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".yaml.tmp")
    temporary.write_text(
        yaml.safe_dump(entries, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def record_change(
    campaign_directory: Path,
    target: str,
    *,
    action: str = "edit",
    reason: str = "",
) -> None:
    if not reason.strip():
        return
    entries = _load_changelog(campaign_directory)
    entries.append(
        {
            "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            "action": action,
            "target": target,
            "reason": reason.strip(),
        }
    )
    _save_changelog(campaign_directory, entries)


def write_with_backup(
    campaign_directory: Path,
    target: Path,
    content: str,
    *,
    action: str = "edit",
    reason: str = "",
) -> Path:
    campaign_directory = campaign_directory.resolve()
    target = target.resolve()
    if not target.is_relative_to(campaign_directory):
        raise CampaignError(f"Target is outside the campaign directory: {target}")
    relative = target.relative_to(campaign_directory)
    if target.exists():
        backup_root = campaign_directory / "backups" / relative.parent
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamped = f"{relative.stem}-{_timestamp()}{relative.suffix}"
        backup = backup_root / timestamped
        try:
            shutil.copy2(target, backup)
        except OSError as exc:
            raise CampaignError(f"Unable to back up {target}: {exc}") from exc
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(target)
    except OSError as exc:
        if temporary.exists():
            temporary.unlink()
        raise CampaignError(f"Unable to write {target}: {exc}") from exc
    record_change(campaign_directory, relative.as_posix(), action=action, reason=reason)
    return target
