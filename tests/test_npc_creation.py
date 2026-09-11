from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.campaigns import load_campaign
from voice_assistant.storage.npc_creation import NpcDraft, create_npc


def _campaign(root: Path) -> Path:
    campaign = root / "campaign"
    characters = campaign / "characters"
    existing = characters / "existing"
    existing.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "id: test\nname: Test\ndefault_npc: existing\n", encoding="utf-8"
    )
    (existing / "profile.md").write_text("# Existing\n", encoding="utf-8")
    return campaign


def _draft(npc_id: str = "guildmaster-vale") -> NpcDraft:
    return NpcDraft(
        id=npc_id,
        name="Guildmaster Vale",
        role="Leader of the merchants guild.",
        personality="Patient and exacting.",
        background="A former caravan factor.",
        goals="Keep trade routes open.",
        public_knowledge="Guild dues increased this year.",
        mood="confident",
        speaking_style="measured",
        gemini_voice="Charon",
    )


def test_create_npc_writes_a_loadable_portable_character(tmp_path: Path) -> None:
    campaign_directory = _campaign(tmp_path)

    destination = create_npc(campaign_directory, _draft())
    campaign = load_campaign(campaign_directory)
    npc = campaign.npc("guildmaster-vale")

    assert destination == campaign_directory / "characters" / "guildmaster-vale"
    assert npc.name == "Guildmaster Vale"
    assert "Leader of the merchants guild." in npc.profile
    assert "A former caravan factor." in npc.profile
    assert "Keep trade routes open." in npc.profile
    assert "Guild dues increased this year." in npc.profile
    assert npc.voice.style == "confident, measured"
    assert npc.voice.providers["gemini"].voice == "Charon"
    assert npc.secrets == ()


def test_create_npc_refuses_to_overwrite_existing_character(tmp_path: Path) -> None:
    campaign_directory = _campaign(tmp_path)
    create_npc(campaign_directory, _draft())

    with pytest.raises(CampaignError, match="already exists"):
        create_npc(campaign_directory, _draft())


@pytest.mark.parametrize("npc_id", ("Guildmaster", "../vale", "vale smith", ""))
def test_create_npc_rejects_unsafe_ids(tmp_path: Path, npc_id: str) -> None:
    with pytest.raises(CampaignError, match="NPC ID"):
        create_npc(_campaign(tmp_path), _draft(npc_id))
