from pathlib import Path

from voice_assistant.services.conversation import (
    build_npc_prompt,
    private_gm_instruction,
    private_gm_request,
    room_id,
)
from voice_assistant.storage.campaigns import load_campaign

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


def test_private_gm_request_explicitly_requests_a_response() -> None:
    request = private_gm_request("What rumors could Elara offer?")

    assert "Respond to the GM's request" in request
    assert "in-character player dialogue" in request
