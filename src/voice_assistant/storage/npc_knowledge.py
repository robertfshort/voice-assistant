from __future__ import annotations

import re
from pathlib import Path

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.change_tracking import write_with_backup

_NPC_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def npc_memory_path(campaign_directory: Path, npc_id: str) -> Path:
    if not _NPC_ID.fullmatch(npc_id):
        raise CampaignError(f"Invalid NPC ID: {npc_id!r}")
    characters = (campaign_directory / "characters").resolve()
    npc_directory = (characters / npc_id).resolve()
    if not npc_directory.is_relative_to(characters) or not npc_directory.is_dir():
        raise CampaignError(f"NPC directory does not exist: {npc_directory}")
    return npc_directory / "memory.md"


def save_npc_knowledge(
    campaign_directory: Path, npc_id: str, content: str, *, reason: str = ""
) -> Path:
    destination = npc_memory_path(campaign_directory, npc_id)
    return write_with_backup(
        campaign_directory,
        destination,
        content,
        action="edit-npc-knowledge",
        reason=reason,
    )


def append_npc_knowledge(
    campaign_directory: Path, npc_id: str, addition: str, *, reason: str = ""
) -> str:
    destination = npc_memory_path(campaign_directory, npc_id)
    try:
        existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
    except OSError as exc:
        raise CampaignError(f"Unable to read NPC knowledge {destination}: {exc}") from exc
    separator = "\n\n" if existing.strip() else ""
    updated = f"{existing.rstrip()}{separator}{addition.strip()}\n"
    save_npc_knowledge(campaign_directory, npc_id, updated, reason=reason)
    return updated
