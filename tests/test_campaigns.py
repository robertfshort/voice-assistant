from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.services.conversation import build_npc_prompt
from voice_assistant.storage.campaigns import (
    create_campaign,
    discover_campaigns,
    load_campaign,
    parse_secrets,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "campaigns"
SAMPLE_CAMPAIGN = SAMPLE_ROOT / "sample"


def test_load_sample_campaign() -> None:
    campaign = load_campaign(SAMPLE_CAMPAIGN)

    assert campaign.manifest.id == "whispering-road"
    assert campaign.manifest.name == "The Whispering Road"
    assert campaign.manifest.default_npc == "elara-voss"
    assert len(campaign.npcs) >= 2
    elara = campaign.npc("elara-voss")
    rell = campaign.npc("captain-rell")
    assert elara.name == "Elara Voss"
    assert elara.voice.providers["gemini"].voice == "Aoede"
    assert elara.secrets[0].id == "missing-caravan"
    assert "Captain Rell" in elara.secrets[0].body
    assert rell.name == "Captain Tomas Rell"
    assert rell.voice.providers["gemini"].voice == "Charon"
    assert rell.secrets[0].id == "compromised-patrol"
    assert "lanterns-rest.md" in campaign.lore
    assert "opening.md" in campaign.scripts
    assert "lanterns-rest.md" in campaign.lore_records
    assert campaign.lore_records["lanterns-rest.md"].visibility == "public"
    assert campaign.lore_records["lanterns-rest.md"].title == "Lanterns Rest"


def test_discover_campaigns_ignores_non_campaign_directories(tmp_path: Path) -> None:
    (tmp_path / "other").mkdir()

    assert discover_campaigns(tmp_path) == ()
    assert len(discover_campaigns(SAMPLE_ROOT)) == 1


def test_campaign_npc_lookup() -> None:
    campaign = load_campaign(SAMPLE_CAMPAIGN)

    assert campaign.npc("elara-voss").name == "Elara Voss"
    with pytest.raises(KeyError):
        campaign.npc("missing")


def test_secret_body_is_separate_from_hint() -> None:
    source = Path("secrets.md")
    secrets = parse_secrets(
        "# Secrets\n\n## hidden-road\n"
        "hint: The abandoned road.\n"
        "mode: deflect\n\n"
        "The road begins behind the mill.\n",
        source,
    )

    assert secrets[0].hint == "The abandoned road."
    assert secrets[0].body == "The road begins behind the mill."


def test_invalid_secret_mode_is_rejected() -> None:
    with pytest.raises(CampaignError, match="invalid mode"):
        parse_secrets(
            "## hidden-road\nhint: The road.\nmode: disclose\n\nSecret body.\n",
            Path("secrets.md"),
        )


def test_missing_default_npc_is_rejected(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    character = campaign / "characters" / "present"
    character.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        "id: test\nname: Test\ndefault_npc: absent\n",
        encoding="utf-8",
    )
    (character / "profile.md").write_text("# Present\n", encoding="utf-8")

    with pytest.raises(CampaignError, match="Default NPC"):
        load_campaign(campaign)


def test_lore_front_matter_is_parsed_and_filters_prompts(tmp_path: Path) -> None:
    (tmp_path / "campaign.yaml").write_text("id: test\nname: Test\n", encoding="utf-8")
    character = tmp_path / "characters" / "npc"
    character.mkdir(parents=True)
    (character / "profile.md").write_text("# NPC\n", encoding="utf-8")
    lore = tmp_path / "lore"
    lore.mkdir()
    (lore / "private.md").write_text(
        "---\n"
        "visibility: gm-only\n"
        "scopes:\n"
        "  - western-border\n"
        "title: Hidden\n"
        "---\n"
        "Secret body.\n",
        encoding="utf-8",
    )
    (lore / "public.md").write_text("Public body.\n", encoding="utf-8")

    campaign = load_campaign(tmp_path)

    assert campaign.lore_records["private.md"].visibility == "gm-only"
    assert campaign.lore_records["private.md"].title == "Hidden"
    assert campaign.lore_records["private.md"].scopes == ("western-border",)
    assert campaign.lore_records["private.md"].body == "Secret body.\n"
    assert campaign.lore_records["public.md"].visibility == "public"
    assert campaign.lore_records["public.md"].title == "Public"
    assert "Secret body." not in build_npc_prompt(campaign, campaign.npc("npc"))
    assert "Public body." in build_npc_prompt(campaign, campaign.npc("npc"))


def test_create_campaign_builds_a_loadable_campaign(tmp_path: Path) -> None:
    create_campaign(tmp_path, "new-campaign", "New Campaign")

    campaigns = discover_campaigns(tmp_path)
    assert len(campaigns) == 1
    assert campaigns[0].manifest.id == "new-campaign"
    assert campaigns[0].manifest.name == "New Campaign"
    assert campaigns[0].npc("narrator").name == "Narrator"
