from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field

from voice_assistant.domain.errors import CampaignError

if TYPE_CHECKING:
    from voice_assistant.domain.models import Npc

_NPC_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PROFILE_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class NpcDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    background: str = ""
    goals: str = ""
    public_knowledge: str = ""
    mood: str = "neutral"
    speaking_style: str = "natural"
    gemini_voice: str = "Aoede"


def _profile(draft: NpcDraft) -> str:
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
    )


def _voice(draft: NpcDraft, existing: dict[str, object] | None = None) -> dict[str, object]:
    voice = dict(existing or {})
    providers_value = voice.get("providers")
    providers = dict(providers_value) if isinstance(providers_value, dict) else {}
    gemini_value = providers.get("gemini")
    gemini = dict(gemini_value) if isinstance(gemini_value, dict) else {}
    gemini["voice"] = draft.gemini_voice
    providers["gemini"] = gemini
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
    return NpcDraft(
        id=npc.id,
        name=npc.name,
        role=sections.get("role", ""),
        personality=sections.get("personality", ""),
        background=sections.get("background", ""),
        goals=sections.get("goals", ""),
        public_knowledge=sections.get("public knowledge", ""),
        mood=style_parts[0] if style_parts else "neutral",
        speaking_style=sections.get("speaking style", "natural"),
        gemini_voice=provider.voice if provider else "Aoede",
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
        profile_temporary = directory / ".profile.md.tmp"
        voice_temporary = directory / ".voice.yaml.tmp"
        profile_temporary.write_text(_profile(draft), encoding="utf-8", newline="\n")
        voice_temporary.write_text(
            yaml.safe_dump(_voice(draft, existing_voice), sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )
        profile_temporary.replace(directory / "profile.md")
        voice_temporary.replace(voice_path)
    except (OSError, yaml.YAMLError) as exc:
        for temporary in (directory / ".profile.md.tmp", directory / ".voice.yaml.tmp"):
            temporary.unlink(missing_ok=True)
        raise CampaignError(f"Unable to update NPC {draft.id}: {exc}") from exc
    return directory
