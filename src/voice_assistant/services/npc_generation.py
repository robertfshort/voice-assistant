from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, SecretStr
from roomkit.providers.ai.base import AIContext, AIMessage
from roomkit.providers.gemini.ai import GeminiAIProvider
from roomkit.providers.gemini.config import GeminiConfig


class NpcExpansion(BaseModel):
    model_config = ConfigDict(frozen=True)

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
        "fields. Add compatible detail without contradicting the input. Return only one JSON "
        "object with string fields: role, personality, background, goals, public_knowledge, mood, "
        f"speaking_style. Draft: {json.dumps(existing, ensure_ascii=False)}"
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
