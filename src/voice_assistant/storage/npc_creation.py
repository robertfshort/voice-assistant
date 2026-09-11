from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from voice_assistant.domain.errors import CampaignError

_NPC_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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

    profile = (
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
    voice = {
        "style": ", ".join(
            value for value in (draft.mood.strip(), draft.speaking_style.strip()) if value
        ),
        "providers": {"gemini": {"voice": draft.gemini_voice}},
    }
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
