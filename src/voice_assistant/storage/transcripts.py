from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from voice_assistant.domain.errors import CampaignError


class TranscriptEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    speaker: str
    text: str
    private: bool = False


def transcript_path(campaign_directory: Path, npc_id: str) -> Path:
    return campaign_directory / "sessions" / f"{npc_id}.jsonl"


def append_transcript(
    campaign_directory: Path,
    npc_id: str,
    speaker: str,
    text: str,
    *,
    private: bool = False,
) -> TranscriptEntry:
    entry = TranscriptEntry(
        timestamp=datetime.now(UTC), speaker=speaker, text=text.strip(), private=private
    )
    path = transcript_path(campaign_directory, npc_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
    except OSError as exc:
        raise CampaignError(f"Unable to append transcript {path}: {exc}") from exc
    return entry


def load_transcript(campaign_directory: Path, npc_id: str) -> tuple[TranscriptEntry, ...]:
    path = transcript_path(campaign_directory, npc_id)
    if not path.exists():
        return ()
    entries: list[TranscriptEntry] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    entries.append(TranscriptEntry.model_validate_json(line))
                except ValueError as exc:
                    raise CampaignError(
                        f"Malformed transcript entry in {path} at line {line_number}: {exc}"
                    ) from exc
    except OSError as exc:
        raise CampaignError(f"Unable to read transcript {path}: {exc}") from exc
    return tuple(entries)
