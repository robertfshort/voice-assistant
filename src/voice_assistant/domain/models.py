from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Secret(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    hint: str
    body: str
    mode: str = "hesitate"
    revealed: str | None = None


class VoiceProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    voice: str = ""
    model: str = ""
    config: str = ""
    speaker_id: int | None = None
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w: float = 0.8


class VoiceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    style: str = ""
    preferred_provider: str = "gemini"
    providers: dict[str, VoiceProviderConfig] = Field(default_factory=dict)


class Npc(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    id: str
    name: str
    directory: Path
    profile: str
    memory: str = ""
    secrets: tuple[Secret, ...] = ()
    affiliations: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    portrait: str | None = None
    archived: bool = False
    home: str = ""
    location: str = ""


class LoreSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    scope: str = ""


class LoreRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    visibility: str = "public"
    scopes: tuple[str, ...] = ()
    provenance: str = "manual"
    status: str = "established"
    body: str = ""
    sections: tuple[LoreSection, ...] = ()

    @field_validator("visibility")
    @classmethod
    def _valid_visibility(cls, value: str) -> str:
        if value not in {"public", "restricted", "secret", "gm-only"}:
            raise ValueError(f"Invalid visibility: {value!r}")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in {"established", "proposed", "archived"}:
            raise ValueError(f"Invalid status: {value!r}")
        return value


class SpeakerProfile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    id: str
    name: str
    path: Path
    profile: str
    affiliations: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    active: bool = False


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
    speakers: tuple[SpeakerProfile, ...] = ()
    lore: dict[str, str] = Field(default_factory=dict)
    lore_records: dict[str, LoreRecord] = Field(default_factory=dict)
    scripts: dict[str, str] = Field(default_factory=dict)
    dictionary: tuple[str, ...] = ()

    def npc(self, npc_id: str) -> Npc:
        for npc in self.npcs:
            if npc.id == npc_id:
                return npc
        raise KeyError(npc_id)
