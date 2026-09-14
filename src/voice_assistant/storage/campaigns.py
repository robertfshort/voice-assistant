from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from voice_assistant.domain.errors import CampaignError
from voice_assistant.domain.models import (
    Campaign,
    CampaignManifest,
    LoreRecord,
    Npc,
    Secret,
    VoiceConfig,
)

_SECRET_HEADING = re.compile(r"^##\s+([a-z0-9][a-z0-9-]*)\s*$", re.MULTILINE)
_SECRET_METADATA = re.compile(r"^(hint|mode|revealed):\s*(.*)$")
_PROFILE_HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_ALLOWED_SECRET_MODES = {"hesitate", "deflect"}


def _read_text(path: Path, *, required: bool = False) -> str:
    if not path.exists():
        if required:
            raise CampaignError(f"Required file is missing: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CampaignError(f"Unable to read {path}: {exc}") from exc


def _read_yaml(path: Path, *, required: bool = False) -> dict[str, Any]:
    text = _read_text(path, required=required)
    if not text:
        return {}
    try:
        value = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise CampaignError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CampaignError(f"Expected a YAML mapping in {path}")
    return value


def parse_secrets(text: str, source: Path) -> tuple[Secret, ...]:
    headings = list(_SECRET_HEADING.finditer(text))
    secrets: list[Secret] = []
    seen: set[str] = set()
    for index, heading in enumerate(headings):
        secret_id = heading.group(1)
        if secret_id in seen:
            raise CampaignError(f"Duplicate secret id {secret_id!r} in {source}")
        seen.add(secret_id)
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        lines = text[heading.end() : end].splitlines()
        metadata: dict[str, str] = {}
        body_start = len(lines)
        for line_index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            match = _SECRET_METADATA.match(stripped)
            if match:
                metadata[match.group(1)] = match.group(2).strip()
                continue
            body_start = line_index
            break
        hint = metadata.get("hint", "")
        mode = metadata.get("mode", "hesitate")
        body = "\n".join(lines[body_start:]).strip()
        if not hint:
            raise CampaignError(f"Secret {secret_id!r} in {source} is missing hint metadata")
        if mode not in _ALLOWED_SECRET_MODES:
            raise CampaignError(f"Secret {secret_id!r} in {source} has invalid mode {mode!r}")
        if not body:
            raise CampaignError(f"Secret {secret_id!r} in {source} has no body")
        secrets.append(
            Secret(
                id=secret_id,
                hint=hint,
                mode=mode,
                revealed=metadata.get("revealed") or None,
                body=body,
            )
        )
    return tuple(secrets)


def _profile_sections(text: str) -> dict[str, str]:
    matches = list(_PROFILE_SECTION.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[heading] = text[match.end() : end].strip()
    return sections


def _parse_affiliations(text: str) -> tuple[str, ...]:
    bullets = _AFFILIATION_ITEM.findall(text)
    if bullets:
        return tuple(bullet.strip() for bullet in bullets if bullet.strip())
    return tuple(
        part.strip() for line in text.splitlines() for part in line.split(",") if part.strip()
    )


def _load_npc(directory: Path) -> Npc:
    profile_path = directory / "profile.md"
    profile = _read_text(profile_path, required=True)
    title = _PROFILE_HEADING.search(profile)
    if title is None:
        raise CampaignError(f"NPC profile has no level-one heading: {profile_path}")
    sections = _profile_sections(profile)
    try:
        voice = VoiceConfig.model_validate(_read_yaml(directory / "voice.yaml"))
    except ValidationError as exc:
        raise CampaignError(
            f"Invalid voice configuration in {directory / 'voice.yaml'}: {exc}"
        ) from exc
    secrets_path = directory / "secrets.md"
    return Npc(
        id=directory.name,
        name=title.group(1).strip(),
        directory=directory.resolve(),
        profile=profile,
        memory=_read_text(directory / "memory.md"),
        secrets=parse_secrets(_read_text(secrets_path), secrets_path),
        affiliations=_parse_affiliations(sections.get("affiliations", "")),
        voice=voice,
    )


_LORE_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_PROFILE_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_AFFILIATION_ITEM = re.compile(r"^[-*]\s+(.+)$", re.MULTILINE)


def _derive_lore_title(lore_id: str) -> str:
    stem = lore_id.rsplit(".", 1)[0] if "." in lore_id else lore_id
    return stem.replace("-", " ").replace("_", " ").title()


def _load_lore_records(directory: Path) -> dict[str, LoreRecord]:
    if not directory.exists():
        return {}
    records: dict[str, LoreRecord] = {}
    files = sorted(path for path in directory.rglob("*") if path.suffix.lower() in {".md", ".txt"})
    for path in files:
        lore_id = path.relative_to(directory).as_posix()
        text = _read_text(path)
        match = _LORE_FRONT_MATTER.match(text)
        if match:
            try:
                metadata = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError as exc:
                raise CampaignError(f"Invalid YAML front matter in {lore_id}: {exc}") from exc
            if not isinstance(metadata, dict):
                raise CampaignError(f"Expected a YAML mapping in front matter of {lore_id}")
            body = match.group(2)
        else:
            metadata = {}
            body = text
        records[lore_id] = LoreRecord(
            id=lore_id,
            title=metadata.get("title") or _derive_lore_title(lore_id),
            visibility=metadata.get("visibility", "public"),
            scopes=tuple(metadata.get("scopes") or ()),
            provenance=metadata.get("provenance", "manual"),
            status=metadata.get("status", "established"),
            body=body,
        )
    return records


def _load_text_directory(directory: Path) -> dict[str, str]:
    if not directory.exists():
        return {}
    files = sorted(path for path in directory.rglob("*") if path.suffix.lower() in {".md", ".txt"})
    return {path.relative_to(directory).as_posix(): _read_text(path) for path in files}


def load_campaign(directory: Path) -> Campaign:
    campaign_directory = directory.expanduser().resolve()
    if not campaign_directory.is_dir():
        raise CampaignError(f"Campaign directory does not exist: {campaign_directory}")
    manifest_path = campaign_directory / "campaign.yaml"
    try:
        manifest = CampaignManifest.model_validate(_read_yaml(manifest_path, required=True))
    except ValidationError as exc:
        raise CampaignError(f"Invalid campaign manifest in {manifest_path}: {exc}") from exc
    characters_directory = campaign_directory / "characters"
    npc_directories = (
        sorted(path for path in characters_directory.iterdir() if path.is_dir())
        if characters_directory.exists()
        else []
    )
    npcs = tuple(_load_npc(path) for path in npc_directories)
    if not npcs:
        raise CampaignError(f"Campaign has no NPC directories: {characters_directory}")
    npc_ids = {npc.id for npc in npcs}
    if manifest.default_npc and manifest.default_npc not in npc_ids:
        raise CampaignError(
            f"Default NPC {manifest.default_npc!r} does not exist in {characters_directory}"
        )
    return Campaign(
        manifest=manifest,
        directory=campaign_directory,
        npcs=npcs,
        lore=_load_text_directory(campaign_directory / "lore"),
        lore_records=_load_lore_records(campaign_directory / "lore"),
        scripts=_load_text_directory(campaign_directory / "scripts"),
    )


def discover_campaigns(root: Path) -> tuple[Campaign, ...]:
    if not root.exists():
        return ()
    campaigns: list[Campaign] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        if (directory / "campaign.yaml").exists():
            campaigns.append(load_campaign(directory))
    return tuple(campaigns)
