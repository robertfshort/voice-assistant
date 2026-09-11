from voice_assistant.services.npc_generation import NpcExpansion, _json_body


def test_json_body_removes_markdown_fence() -> None:
    assert _json_body('```json\n{"role": "keeper"}\n```') == '{"role": "keeper"}'


def test_npc_expansion_requires_all_review_fields() -> None:
    expansion = NpcExpansion.model_validate(
        {
            "role": "Guildmaster",
            "personality": "Patient",
            "background": "Former factor",
            "goals": "Protect trade",
            "public_knowledge": "Collects guild dues",
            "mood": "confident",
            "speaking_style": "measured",
        }
    )

    assert expansion.goals == "Protect trade"
    assert expansion.public_knowledge == "Collects guild dues"
