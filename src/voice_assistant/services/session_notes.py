from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from roomkit.providers.ai.base import AIContext, AIMessage

from voice_assistant.services.npc_generation import _json_body
from voice_assistant.services.npc_generation import _provider as _gemini_provider
from voice_assistant.storage.transcripts import TranscriptEntry


class SessionNotes(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str
    proposed_memory: str = ""
    proposed_lore: tuple[str, ...] = ()


def _format_transcript(entries: tuple[TranscriptEntry, ...]) -> str:
    return "\n".join(f"- {entry.speaker}: {entry.text}" for entry in entries if not entry.private)


async def propose_session_notes(
    api_key: str, entries: tuple[TranscriptEntry, ...]
) -> SessionNotes:
    if not entries:
        return SessionNotes(summary="No transcript entries to summarize.")
    transcript = _format_transcript(entries)
    prompt = (
        "Review this tabletop RPG session transcript. Return only one JSON object with a string "
        "field 'summary', a string field 'proposed_memory' (new facts about the active NPC that "
        "could be appended to their memory), and a list of strings 'proposed_lore' (public facts "
        "that could become established campaign lore). Do not include secrets, private GM "
        "direction, or uncertain rumors as lore. Transcript:\n"
        f"{transcript}"
    )
    provider = _gemini_provider(api_key, 1400)
    response = await provider.generate(
        AIContext(
            system_prompt="You help a GM summarize play sessions and propose public knowledge.",
            messages=[AIMessage(role="user", content=prompt)],
            temperature=0.6,
            max_tokens=1400,
        )
    )
    return SessionNotes.model_validate_json(_json_body(response.content))
