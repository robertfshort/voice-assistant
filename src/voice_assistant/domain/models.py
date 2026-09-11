from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Secret(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    hint: str
    body: str
    mode: str = "hesitate"
    revealed: str | None = None


class VoiceProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    voice: str


class VoiceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    style: str = ""
    providers: dict[str, VoiceProviderConfig] = Field(default_factory=dict)


class Npc(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    id: str
    name: str
    directory: Path
    profile: str
    memory: str = ""
    secrets: tuple[Secret, ...] = ()
    voice: VoiceConfig = Field(default_factory=VoiceConfig)


class CampaignManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    default_npc: str | None = None


class Campaign(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    manifest: CampaignManifest
    directory: Path
    npcs: tuple[Npc, ...]
    lore: dict[str, str] = Field(default_factory=dict)
    scripts: dict[str, str] = Field(default_factory=dict)

    def npc(self, npc_id: str) -> Npc:
        for npc in self.npcs:
            if npc.id == npc_id:
                return npc
        raise KeyError(npc_id)
