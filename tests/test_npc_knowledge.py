from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.npc_knowledge import (
    append_npc_knowledge,
    npc_memory_path,
    save_npc_knowledge,
)


def _campaign_with_npc(root: Path) -> Path:
    npc_directory = root / "characters" / "elara"
    npc_directory.mkdir(parents=True)
    (npc_directory / "memory.md").write_text("# Memory\n\nOld fact.\n", encoding="utf-8")
    return root


def test_save_npc_knowledge_replaces_memory_atomically(tmp_path: Path) -> None:
    campaign = _campaign_with_npc(tmp_path)

    path = save_npc_knowledge(campaign, "elara", "# Memory\n\nNew fact.\n")

    assert path.read_text(encoding="utf-8") == "# Memory\n\nNew fact.\n"
    assert not path.with_suffix(".md.tmp").exists()


def test_append_npc_knowledge_preserves_existing_content(tmp_path: Path) -> None:
    campaign = _campaign_with_npc(tmp_path)

    updated = append_npc_knowledge(campaign, "elara", "Learned at the table.")

    assert "Old fact." in updated
    assert updated.endswith("Learned at the table.\n")


@pytest.mark.parametrize("npc_id", ("../elara", "Elara", "elara/voss", ""))
def test_npc_memory_path_rejects_unsafe_ids(tmp_path: Path, npc_id: str) -> None:
    with pytest.raises(CampaignError, match="Invalid NPC ID"):
        npc_memory_path(tmp_path, npc_id)


def test_npc_memory_path_requires_existing_npc(tmp_path: Path) -> None:
    with pytest.raises(CampaignError, match="does not exist"):
        npc_memory_path(tmp_path, "missing")
