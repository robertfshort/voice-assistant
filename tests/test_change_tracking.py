from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.change_tracking import record_change, write_with_backup


def test_write_with_backup_creates_a_dated_copy_and_writes_new_content(
    tmp_path: Path,
) -> None:
    original = tmp_path / "lore" / "crossroads.md"
    original.parent.mkdir()
    original.write_text("Old lore", encoding="utf-8")

    result = write_with_backup(
        tmp_path, original, "New lore.", action="edit-lore", reason="Updated"
    )

    assert result == original
    assert original.read_text(encoding="utf-8") == "New lore."
    backups = list((tmp_path / "backups" / "lore").iterdir())
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "Old lore"
    changelog = (tmp_path / "changelog.yaml").read_text(encoding="utf-8")
    assert "Updated" in changelog
    assert "edit-lore" in changelog
    assert "lore/crossroads.md" in changelog


def test_write_with_backup_without_reason_does_not_record_changelog(
    tmp_path: Path,
) -> None:
    target = tmp_path / "lore" / "empty.md"
    target.parent.mkdir()
    target.write_text("A", encoding="utf-8")

    write_with_backup(tmp_path, target, "B")

    assert not (tmp_path / "changelog.yaml").exists()


def test_write_with_backup_rejects_targets_outside_campaign(tmp_path: Path) -> None:
    outside = tmp_path / ".." / "outside.md"
    with pytest.raises(CampaignError, match="outside the campaign"):
        write_with_backup(tmp_path, outside, "content")


def test_record_change_appends_to_changelog(tmp_path: Path) -> None:
    record_change(tmp_path, "lore/notes.md", action="edit-lore", reason="First")
    record_change(tmp_path, "lore/notes.md", action="edit-lore", reason="Second")

    changelog = (tmp_path / "changelog.yaml").read_text(encoding="utf-8")
    assert changelog.count("reason:") == 2
    assert "First" in changelog
    assert "Second" in changelog
