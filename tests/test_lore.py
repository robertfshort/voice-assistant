from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.lore import lore_path, save_lore


def test_save_lore_replaces_existing_file_atomically(tmp_path: Path) -> None:
    lore_directory = tmp_path / "lore"
    lore_directory.mkdir()
    source = lore_directory / "crossroads.md"
    source.write_text("Old lore", encoding="utf-8")

    result = save_lore(tmp_path, "crossroads.md", "# Crossroads\n\nNew lore.\n")

    assert result == source
    assert source.read_text(encoding="utf-8") == "# Crossroads\n\nNew lore.\n"
    assert not (lore_directory / "crossroads.md.tmp").exists()


@pytest.mark.parametrize(
    "lore_id",
    ("../secrets.md", "/absolute.md", "notes.yaml", "folder/../../outside.md"),
)
def test_lore_path_rejects_unsafe_or_unsupported_names(tmp_path: Path, lore_id: str) -> None:
    with pytest.raises(CampaignError, match="Invalid lore file name"):
        lore_path(tmp_path, lore_id)


def test_save_lore_will_not_create_an_unreviewed_entry(tmp_path: Path) -> None:
    with pytest.raises(CampaignError, match="does not exist"):
        save_lore(tmp_path, "new.md", "Unreviewed lore")
