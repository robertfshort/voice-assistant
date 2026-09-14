from __future__ import annotations

import re
from pathlib import Path

from voice_assistant.domain.models import LoreRecord, Npc
from voice_assistant.storage.change_tracking import record_change
from voice_assistant.storage.lore import create_lore

_SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _section_text(profile: str, heading: str) -> str:
    matches = list(_SECTION_HEADING.finditer(profile))
    for index, match in enumerate(matches):
        if match.group(1).strip().lower() == heading.lower():
            end = matches[index + 1].start() if index + 1 < len(matches) else len(profile)
            return profile[match.end() : end].strip()
    return ""


def propose_npc_lore(npc: Npc) -> LoreRecord | None:
    role = _section_text(npc.profile, "Role")
    public = _section_text(npc.profile, "Public knowledge")
    if not role and not public:
        return None
    body_parts: list[str] = []
    if role:
        body_parts.append(f"## Role\n\n{role}")
    if public:
        body_parts.append(f"## Public knowledge\n\n{public}")
    return LoreRecord(
        id=f"npcs/{npc.id}.md",
        title=npc.name,
        body="\n\n".join(body_parts),
        visibility="public",
        provenance="npc-derived",
        status="proposed",
    )


def render_lore_file(record: LoreRecord) -> str:
    return (
        "---\n"
        f"visibility: {record.visibility}\n"
        f"provenance: {record.provenance}\n"
        f"status: {record.status}\n"
        f"title: {record.title}\n"
        "---\n\n"
        f"{record.body}\n"
    )


def save_lore_proposal(
    campaign_directory: Path, lore_id: str, content: str, *, reason: str = ""
) -> Path:
    destination = create_lore(campaign_directory, lore_id, content)
    record_change(
        campaign_directory,
        f"lore/{lore_id}",
        action="npc-proposed-lore",
        reason=reason or "NPC public fact proposal",
    )
    return destination
