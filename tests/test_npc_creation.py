from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.campaigns import load_campaign
from voice_assistant.storage.npc_creation import NpcDraft, create_npc, draft_from_npc, update_npc


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
        affiliations="- Merchants Guild\n- Order of the Rose",
        mood="confident",
        speaking_style="measured",
        preferred_voice_provider="piper",
        gemini_voice="Charon",
        piper_voice="guildmaster",
        piper_model="voices/vale.onnx",
        piper_config="voices/vale.onnx.json",
        piper_speaker_id=2,
        piper_sentence_silence=0.25,
        piper_sample_rate=48000,
        piper_channels=2,
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
    assert "Merchants Guild" in npc.profile
    assert npc.affiliations == ("Merchants Guild", "Order of the Rose")
    assert npc.voice.style == "confident, measured"
    assert npc.voice.preferred_provider == "piper"
    assert npc.voice.providers["gemini"].voice == "Charon"
    assert npc.voice.providers["piper"].voice == "guildmaster"
    assert npc.voice.providers["piper"].model == "voices/vale.onnx"
    assert npc.voice.providers["piper"].speaker_id == 2
    assert npc.voice.providers["piper"].sentence_silence == 0.25
    assert npc.voice.providers["piper"].sample_rate == 48000
    assert npc.voice.providers["piper"].channels == 2
    assert npc.secrets == ()


def test_create_npc_refuses_to_overwrite_existing_character(tmp_path: Path) -> None:
    campaign_directory = _campaign(tmp_path)
    create_npc(campaign_directory, _draft())

    with pytest.raises(CampaignError, match="already exists"):
        create_npc(campaign_directory, _draft())


def test_update_npc_changes_profile_and_voice_but_preserves_private_files(tmp_path: Path) -> None:
    campaign_directory = _campaign(tmp_path)
    create_npc(campaign_directory, _draft())
    npc_directory = campaign_directory / "characters" / "guildmaster-vale"
    (npc_directory / "memory.md").write_text("Private memory", encoding="utf-8")
    (npc_directory / "secrets.md").write_text("# Preserved secrets\n", encoding="utf-8")
    (npc_directory / "voice.yaml").write_text(
        "style: old\nproviders:\n  gemini:\n    voice: Aoede\n  local:\n    voice: custom\n",
        encoding="utf-8",
    )
    draft = _draft().model_copy(update={"name": "Mara Vale", "gemini_voice": "Kore"})

    update_npc(campaign_directory, draft)
    npc = load_campaign(campaign_directory).npc("guildmaster-vale")

    assert npc.name == "Mara Vale"
    assert npc.voice.providers["gemini"].voice == "Kore"
    assert npc.voice.providers["local"].voice == "custom"
    assert (npc_directory / "memory.md").read_text(encoding="utf-8") == "Private memory"
    assert (npc_directory / "secrets.md").read_text(encoding="utf-8") == "# Preserved secrets\n"


def test_draft_from_npc_reads_editable_profile_fields(tmp_path: Path) -> None:
    campaign_directory = _campaign(tmp_path)
    create_npc(campaign_directory, _draft())

    draft = draft_from_npc(load_campaign(campaign_directory).npc("guildmaster-vale"))

    assert draft.name == "Guildmaster Vale"
    assert draft.role == "Leader of the merchants guild."
    assert draft.background == "A former caravan factor."
    assert draft.affiliations == "- Merchants Guild\n- Order of the Rose"
    assert draft.preferred_voice_provider == "piper"
    assert draft.gemini_voice == "Charon"
    assert draft.piper_voice == "guildmaster"
    assert draft.piper_model == "voices/vale.onnx"
    assert draft.piper_speaker_id == 2
    assert draft.piper_sentence_silence == 0.25
    assert draft.piper_sample_rate == 48000
    assert draft.piper_channels == 2


def test_create_npc_copies_portrait_image(tmp_path: Path) -> None:
    campaign_directory = _campaign(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"dummy")
    draft = _draft().model_copy(update={"portrait": str(source)})

    create_npc(campaign_directory, draft)
    npc = load_campaign(campaign_directory).npc("guildmaster-vale")

    assert npc.portrait == "portrait.png"
    assert (npc.directory / "portrait.png").exists()


@pytest.mark.parametrize("npc_id", ("Guildmaster", "../vale", "vale smith", ""))
def test_create_npc_rejects_unsafe_ids(tmp_path: Path, npc_id: str) -> None:
    with pytest.raises(CampaignError, match="NPC ID"):
        create_npc(_campaign(tmp_path), _draft(npc_id))
