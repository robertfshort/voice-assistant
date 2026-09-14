from pathlib import Path

from voice_assistant.domain.models import (
    Campaign,
    CampaignManifest,
    LoreRecord,
    Npc,
    VoiceConfig,
)
from voice_assistant.services.conversation import (
    build_npc_prompt,
    private_gm_instruction,
    private_gm_request,
    room_id,
)
from voice_assistant.storage.campaigns import load_campaign


def _campaign_with_lore(records: dict[str, LoreRecord]) -> Campaign:
    npc = Npc(
        id="npc", name="NPC", directory=Path("npc"), profile="# NPC\nNPC", voice=VoiceConfig()
    )
    return Campaign(
        manifest=CampaignManifest(id="c", name="C"),
        directory=Path("campaign"),
        npcs=(npc,),
        lore={id: record.body for id, record in records.items()},
        lore_records=records,
    )


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_room_id_is_stable_and_isolated() -> None:
    assert room_id("campaign", "elara") == room_id("campaign", "elara")
    assert room_id("campaign", "elara") != room_id("campaign", "rell")
    assert room_id("other", "elara") != room_id("campaign", "elara")


def test_prompt_includes_context_but_not_unrevealed_secret_body() -> None:
    campaign = load_campaign(REPOSITORY_ROOT / "examples" / "campaigns" / "sample")
    npc = campaign.npc("elara-voss")

    prompt = build_npc_prompt(campaign, npc)

    assert "Elara Voss" in prompt
    assert "Lantern's Rest" in prompt
    assert npc.voice.style in prompt
    assert "missing-caravan" in prompt
    assert npc.secrets[0].body not in prompt


def test_npc_prompts_isolate_voice_memory_and_secret_hints() -> None:
    campaign = load_campaign(REPOSITORY_ROOT / "examples" / "campaigns" / "sample")
    elara_prompt = build_npc_prompt(campaign, campaign.npc("elara-voss"))
    rell_prompt = build_npc_prompt(campaign, campaign.npc("captain-rell"))

    assert "guarded, measured, dry humor" in elara_prompt
    assert "formal, controlled, quietly authoritative" not in elara_prompt
    assert "missing-caravan" in elara_prompt
    assert "compromised-patrol" not in elara_prompt
    assert "formal, controlled, quietly authoritative" in rell_prompt
    assert "guarded, measured, dry humor" not in rell_prompt
    assert "compromised-patrol" in rell_prompt
    assert "missing-caravan" not in rell_prompt


def test_private_gm_instruction_is_explicitly_out_of_character() -> None:
    instruction = private_gm_instruction("Become more cooperative.")

    assert "player did not say or hear this" in instruction
    assert "Become more cooperative." in instruction


def test_private_direction_can_be_baked_into_prompt_without_requesting_a_turn() -> None:
    campaign = load_campaign(REPOSITORY_ROOT / "examples" / "campaigns" / "sample")
    prompt = build_npc_prompt(
        campaign,
        campaign.npc("elara-voss"),
        private_directions=("Become more cooperative.",),
    )

    assert "# Private GM direction" in prompt
    assert "Become more cooperative." in prompt
    assert "never quote" in prompt.lower()


def test_prompt_excludes_gm_only_and_secret_lore() -> None:
    records = {
        "public.md": LoreRecord(id="public.md", title="Public", body="Known."),
        "secret.md": LoreRecord(
            id="secret.md", title="Secret", visibility="secret", body="Hidden."
        ),
        "gm.md": LoreRecord(id="gm.md", title="GM", visibility="gm-only", body="GM only."),
    }
    campaign = _campaign_with_lore(records)
    prompt = build_npc_prompt(campaign, campaign.npc("npc"))

    assert "Known." in prompt
    assert "Hidden." not in prompt
    assert "GM only." not in prompt


def test_prompt_includes_public_and_restricted_lore() -> None:
    records = {
        "public.md": LoreRecord(id="public.md", title="Public", body="Known."),
        "restricted.md": LoreRecord(
            id="restricted.md", title="Restricted", visibility="restricted", body="Rumored."
        ),
    }
    campaign = _campaign_with_lore(records)
    prompt = build_npc_prompt(campaign, campaign.npc("npc"))

    assert "Known." in prompt
    assert "Rumored." in prompt


def test_private_gm_request_explicitly_requests_a_response() -> None:
    request = private_gm_request("What rumors could Elara offer?")

    assert "Respond to the GM's request" in request
    assert "in-character player dialogue" in request
