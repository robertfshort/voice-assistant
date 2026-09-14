from pathlib import Path

from voice_assistant.domain.models import LoreRecord, Npc, VoiceConfig
from voice_assistant.storage.npc_lore_proposals import (
    propose_npc_lore,
    render_lore_file,
    save_lore_proposal,
)


def _npc(profile: str, npc_id: str = "elara-voss", name: str = "Elara Voss") -> Npc:
    return Npc(
        id=npc_id,
        name=name,
        directory=Path("npc"),
        profile=profile,
        voice=VoiceConfig(),
    )


def test_propose_npc_lore_extracts_role_and_public_knowledge() -> None:
    npc = _npc(
        "# Elara Voss\n\n"
        "## Role\n\n"
        "Tavern keeper at the Lantern's Rest.\n\n"
        "## Public knowledge\n\n"
        "- Local rumors.\n- Caravan schedules.\n"
    )

    proposed = propose_npc_lore(npc)

    assert proposed is not None
    assert proposed.title == "Elara Voss"
    assert proposed.id == "npcs/elara-voss.md"
    assert proposed.visibility == "public"
    assert proposed.provenance == "npc-derived"
    assert proposed.status == "proposed"
    assert "Tavern keeper at the Lantern's Rest" in proposed.body
    assert "Local rumors" in proposed.body


def test_propose_npc_lore_returns_none_without_public_sections() -> None:
    npc = _npc("# Elara Voss\n\n## Personality\n\nGuarded.\n")

    assert propose_npc_lore(npc) is None


def test_render_lore_file_includes_front_matter() -> None:
    record = LoreRecord(
        id="npcs/elara.md",
        title="Elara Voss",
        visibility="public",
        provenance="npc-derived",
        status="proposed",
        body="## Role\n\nTavern keeper.",
    )

    content = render_lore_file(record)

    assert "visibility: public" in content
    assert "provenance: npc-derived" in content
    assert "status: proposed" in content
    assert "title: Elara Voss" in content
    assert "## Role" in content
    assert "Tavern keeper" in content


def test_save_lore_proposal_creates_lore_and_logs_change(tmp_path: Path) -> None:
    record = LoreRecord(
        id="npcs/elara.md",
        title="Elara Voss",
        body="## Role\n\nTavern keeper.",
    )
    content = render_lore_file(record)

    result = save_lore_proposal(tmp_path, "npcs/elara.md", content)

    assert result == tmp_path / "lore" / "npcs" / "elara.md"
    assert result.read_text(encoding="utf-8") == content
    changelog = (tmp_path / "changelog.yaml").read_text(encoding="utf-8")
    assert "npc-proposed-lore" in changelog
    assert "lore/npcs/elara.md" in changelog
