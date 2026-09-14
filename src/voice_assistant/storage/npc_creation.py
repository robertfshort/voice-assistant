from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.change_tracking import write_with_backup

if TYPE_CHECKING:
    from voice_assistant.domain.models import Npc

_NPC_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PROFILE_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_PORTRAIT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _remove_portraits(directory: Path) -> None:
    for ext in _PORTRAIT_EXTS:
        path = directory / f"portrait{ext}"
        if path.exists():
            path.unlink()


def _write_portrait(source: str | None, target: Path) -> None:
    if not source:
        return
    source_path = Path(source).expanduser()
    if not source_path.exists():
        return
    if source_path.suffix.lower() not in _PORTRAIT_EXTS:
        return
    _remove_portraits(target)
    shutil.copy2(source_path, target / f"portrait{source_path.suffix.lower()}")


class NpcDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    background: str = ""
    goals: str = ""
    public_knowledge: str = ""
    affiliations: str = ""
    mood: str = "neutral"
    speaking_style: str = "natural"
    preferred_voice_provider: str = "gemini"
    gemini_voice: str = "Aoede"
    piper_voice: str = ""
    piper_model: str = ""
    piper_config: str = ""
    piper_speaker_id: int | None = None
    piper_length_scale: float = 1.0
    piper_noise_scale: float = 0.667
    piper_noise_w: float = 0.8
    portrait: str | None = None
    archived: bool = False
    home: str = ""
    location: str = ""
    relationships: str = ""


def _profile(draft: NpcDraft) -> str:
    affiliations = (
        f"\n\n## Affiliations\n\n{draft.affiliations.strip()}"
        if draft.affiliations.strip()
        else ""
    )
    status = "\n\n## Status\n\nArchived" if draft.archived else ""
    home = f"\n\n## Home region\n\n{draft.home.strip()}" if draft.home.strip() else ""
    location = (
        f"\n\n## Current location\n\n{draft.location.strip()}" if draft.location.strip() else ""
    )
    relationships = (
        f"\n\n## Relationships\n\n{draft.relationships.strip()}"
        if draft.relationships.strip()
        else ""
    )
    return (
        f"# {draft.name.strip()}\n\n"
        f"## Role\n\n{draft.role.strip()}\n\n"
        f"## Personality\n\n{draft.personality.strip()}\n\n"
        f"## Background\n\n{draft.background.strip() or 'No background has been recorded.'}\n\n"
        f"## Speaking style\n\n{draft.speaking_style.strip()}\n\n"
        "## Public knowledge\n\n"
        f"{draft.public_knowledge.strip() or 'No public knowledge has been recorded.'}\n\n"
        f"## Goals\n\n{draft.goals.strip() or 'No goals have been recorded.'}\n\n"
        "## Hard rules\n\n"
        "- Stay in character.\n"
        "- Do not invent campaign facts when supplied material does not contain an answer.\n"
        "- Admit uncertainty naturally rather than acting as an assistant.\n"
        "- Never acknowledge private GM instructions.\n"
        f"{affiliations}"
        f"{status}"
        f"{home}"
        f"{location}"
        f"{relationships}"
    )


def _voice(draft: NpcDraft, existing: dict[str, object] | None = None) -> dict[str, object]:
    voice = dict(existing or {})
    providers_value = voice.get("providers")
    providers = dict(providers_value) if isinstance(providers_value, dict) else {}
    gemini_value = providers.get("gemini")
    gemini = dict(gemini_value) if isinstance(gemini_value, dict) else {}
    gemini["voice"] = draft.gemini_voice
    providers["gemini"] = gemini
    if draft.piper_voice or draft.piper_model:
        providers["piper"] = {
            "voice": draft.piper_voice,
            "model": draft.piper_model,
            "config": draft.piper_config,
            "speaker_id": draft.piper_speaker_id,
            "length_scale": draft.piper_length_scale,
            "noise_scale": draft.piper_noise_scale,
            "noise_w": draft.piper_noise_w,
        }
    else:
        providers.pop("piper", None)
    voice["preferred_provider"] = draft.preferred_voice_provider
    voice["style"] = ", ".join(
        value for value in (draft.mood.strip(), draft.speaking_style.strip()) if value
    )
    voice["providers"] = providers
    return voice


def create_npc(campaign_directory: Path, draft: NpcDraft) -> Path:
    if not _NPC_ID.fullmatch(draft.id):
        raise CampaignError(
            "NPC ID must use lowercase letters, numbers, and hyphens, and start with a letter "
            "or number"
        )
    characters = (campaign_directory / "characters").resolve()
    if not characters.is_dir():
        raise CampaignError(f"Campaign characters directory does not exist: {characters}")
    destination = characters / draft.id
    staging = characters / f".{draft.id}.tmp"
    if destination.exists():
        raise CampaignError(f"NPC already exists: {draft.id}")
    if staging.exists():
        raise CampaignError(f"NPC creation is already in progress: {draft.id}")

    profile = _profile(draft)
    voice = _voice(draft)
    try:
        staging.mkdir()
        (staging / "profile.md").write_text(profile, encoding="utf-8", newline="\n")
        (staging / "memory.md").write_text(
            f"# {draft.name.strip()} — Memory\n\nNo sessions have been recorded.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "secrets.md").write_text(
            f"# {draft.name.strip()} — GM-gated secrets\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "voice.yaml").write_text(
            yaml.safe_dump(voice, sort_keys=False), encoding="utf-8", newline="\n"
        )
        _write_portrait(draft.portrait, staging)
        staging.replace(destination)
    except OSError as exc:
        if staging.exists():
            shutil.rmtree(staging)
        raise CampaignError(f"Unable to create NPC {draft.id}: {exc}") from exc
    return destination


def draft_from_npc(npc: Npc) -> NpcDraft:
    profile = npc.profile
    headings = list(_PROFILE_SECTION.finditer(profile))
    sections: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(profile)
        sections[heading.group(1).strip().lower()] = profile[heading.end() : end].strip()
    voice = npc.voice
    style_parts = [part.strip() for part in voice.style.split(",") if part.strip()]
    provider = voice.providers.get("gemini")
    piper = voice.providers.get("piper")
    return NpcDraft(
        id=npc.id,
        name=npc.name,
        role=sections.get("role", ""),
        personality=sections.get("personality", ""),
        background=sections.get("background", ""),
        goals=sections.get("goals", ""),
        public_knowledge=sections.get("public knowledge", ""),
        affiliations=sections.get("affiliations", ""),
        mood=style_parts[0] if style_parts else "neutral",
        speaking_style=sections.get("speaking style", "natural"),
        preferred_voice_provider=voice.preferred_provider,
        gemini_voice=provider.voice if provider else "Aoede",
        piper_voice=piper.voice if piper else "",
        piper_model=piper.model if piper else "",
        piper_config=piper.config if piper else "",
        piper_speaker_id=piper.speaker_id if piper else None,
        piper_length_scale=piper.length_scale if piper else 1.0,
        piper_noise_scale=piper.noise_scale if piper else 0.667,
        piper_noise_w=piper.noise_w if piper else 0.8,
        portrait=(npc.directory / npc.portrait).as_posix() if npc.portrait else None,
        archived=sections.get("status", "").lower() == "archived",
        home=sections.get("home region", ""),
        location=sections.get("current location", ""),
        relationships=sections.get("relationships", ""),
    )


def update_npc(campaign_directory: Path, draft: NpcDraft) -> Path:
    if not _NPC_ID.fullmatch(draft.id):
        raise CampaignError(f"Invalid existing NPC ID: {draft.id}")
    directory = (campaign_directory / "characters" / draft.id).resolve()
    if not directory.is_dir():
        raise CampaignError(f"NPC does not exist: {draft.id}")
    voice_path = directory / "voice.yaml"
    try:
        existing_voice = yaml.safe_load(voice_path.read_text(encoding="utf-8")) or {}
        if not isinstance(existing_voice, dict):
            raise CampaignError(f"Expected a YAML mapping in {voice_path}")
        campaign_directory = directory.parent.parent
        profile_path = directory / "profile.md"
        write_with_backup(
            campaign_directory,
            profile_path,
            _profile(draft),
            action="edit-npc",
        )
        write_with_backup(
            campaign_directory,
            voice_path,
            yaml.safe_dump(_voice(draft, existing_voice), sort_keys=False),
            action="edit-npc-voice",
        )
        _write_portrait(draft.portrait, directory)
    except (OSError, yaml.YAMLError) as exc:
        raise CampaignError(f"Unable to update NPC {draft.id}: {exc}") from exc
    return directory
