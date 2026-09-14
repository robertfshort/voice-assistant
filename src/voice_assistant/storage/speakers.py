from __future__ import annotations

import re
from pathlib import Path

import yaml

from voice_assistant.domain.errors import CampaignError
from voice_assistant.domain.models import SpeakerProfile
from voice_assistant.storage.change_tracking import write_with_backup

_ID_SANITIZE = re.compile(r"[^a-z0-9-]+")
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _safe_speaker_id(value: str) -> str:
    slug = _ID_SANITIZE.sub("-", value.lower()).strip("-")
    if not slug:
        raise CampaignError("Speaker ID must contain letters or numbers")
    return slug


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CampaignError(f"Unable to read {path}: {exc}") from exc


def _load_speaker(path: Path) -> SpeakerProfile:
    text = _read_text(path)
    match = _FRONT_MATTER.match(text)
    if match:
        try:
            metadata = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            raise CampaignError(f"Invalid YAML front matter in {path}: {exc}") from exc
        body = match.group(2).strip()
    else:
        metadata = {}
        body = text.strip()
    if not isinstance(metadata, dict):
        raise CampaignError(f"Expected a YAML mapping in {path}")
    speaker_id = _safe_speaker_id(path.stem)
    return SpeakerProfile(
        id=speaker_id,
        name=metadata.get("name") or speaker_id,
        path=path,
        profile=body,
        affiliations=tuple(metadata.get("affiliations") or ()),
        relationships=tuple(metadata.get("relationships") or ()),
        active=bool(metadata.get("active", False)),
    )


def load_speakers(directory: Path) -> tuple[SpeakerProfile, ...]:
    pcs = directory / "pcs"
    if not pcs.exists():
        return ()
    files = sorted(path for path in pcs.iterdir() if path.suffix.lower() == ".md")
    return tuple(_load_speaker(path) for path in files)


def _render_speaker(speaker: SpeakerProfile) -> str:
    front: dict[str, object] = {"name": speaker.name}
    if speaker.affiliations:
        front["affiliations"] = list(speaker.affiliations)
    if speaker.relationships:
        front["relationships"] = list(speaker.relationships)
    if speaker.active:
        front["active"] = True
    return (
        "---\n"
        f"{yaml.safe_dump(front, sort_keys=False, allow_unicode=True)}"
        "---\n\n"
        f"{speaker.profile.strip()}\n"
    )


def create_speaker(campaign_directory: Path, speaker_id: str, name: str) -> SpeakerProfile:
    speaker_id = _safe_speaker_id(speaker_id)
    path = (campaign_directory / "pcs" / f"{speaker_id}.md").resolve()
    if path.exists():
        raise CampaignError(f"Speaker already exists: {speaker_id}")
    speaker = SpeakerProfile(
        id=speaker_id,
        name=name,
        path=path,
        profile="",
        active=False,
    )
    save_speaker(campaign_directory, speaker)
    return speaker


def save_speaker(campaign_directory: Path, speaker: SpeakerProfile, *, reason: str = "") -> Path:
    path = speaker.path
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_with_backup(
        campaign_directory,
        path,
        _render_speaker(speaker),
        action="edit-speaker",
        reason=reason,
    )
