from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, SecretStr
from roomkit.providers.ai.base import AIContext, AIMessage
from roomkit.providers.gemini.ai import GeminiAIProvider
from roomkit.providers.gemini.config import GeminiConfig

from voice_assistant.services.gemini_voices import GEMINI_VOICES


class NpcExpansion(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    role: str
    personality: str
    background: str
    goals: str
    public_knowledge: str
    mood: str
    speaking_style: str


def _json_body(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines)
    return value


async def expand_npc(api_key: str, existing: dict[str, str]) -> NpcExpansion:
    provider = GeminiAIProvider(
        GeminiConfig(api_key=SecretStr(api_key), model="gemini-3.1-flash-lite", max_tokens=1400)
    )
    prompt = (
        "Expand this tabletop RPG NPC draft. Preserve useful GM-authored details and fill empty "
        "fields. Choose a coherent character name first, then use that identity consistently. "
        "Add compatible detail without contradicting the input. Return only one JSON object with "
        "string fields: name, role, personality, background, goals, public_knowledge, mood, and "
        "speaking_style. Draft: "
        f"{json.dumps(existing, ensure_ascii=False)}"
    )
    try:
        response = await provider.generate(
            AIContext(
                system_prompt=(
                    "You help a game master draft concise, internally consistent campaign NPCs. "
                    "Do not include secrets in public knowledge. Output valid JSON only."
                ),
                messages=[AIMessage(role="user", content=prompt)],
                temperature=0.8,
                max_tokens=1400,
            )
        )
        return NpcExpansion.model_validate_json(_json_body(response.content))
    finally:
        await provider.close()


async def generate_npc_field(
    api_key: str,
    field: str,
    existing: dict[str, str],
    *,
    flesh_out: bool = False,
) -> str:
    allowed = {
        "name",
        "role",
        "personality",
        "background",
        "goals",
        "public_knowledge",
        "mood",
        "speaking_style",
        "gemini_voice",
    }
    if field not in allowed:
        raise ValueError(f"Unsupported NPC field: {field}")
    current = existing.get(field, "")
    action = (
        "Preserve every useful existing detail and flesh it out with compatible specifics."
        if flesh_out
        else "Generate a replacement value, overwriting the existing value."
    )
    constraint = (
        f" Choose exactly one of: {', '.join(GEMINI_VOICES)}." if field == "gemini_voice" else ""
    )
    public_rule = " Do not include secrets." if field == "public_knowledge" else ""
    prompt = (
        f"Generate only the {field} field for this tabletop RPG NPC. {action}{constraint}"
        f"{public_rule} Return only the field value with no label or Markdown fence. "
        f"Current value: {current!r}. Other fields: {json.dumps(existing, ensure_ascii=False)}"
    )
    provider = GeminiAIProvider(
        GeminiConfig(api_key=SecretStr(api_key), model="gemini-3.1-flash-lite", max_tokens=700)
    )
    try:
        response = await provider.generate(
            AIContext(
                system_prompt=(
                    "You help a game master create concise, internally consistent campaign NPCs."
                ),
                messages=[AIMessage(role="user", content=prompt)],
                temperature=0.8,
                max_tokens=700,
            )
        )
        return response.content.strip()
    finally:
        await provider.close()
