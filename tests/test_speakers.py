from pathlib import Path

import pytest

from voice_assistant.domain.errors import CampaignError
from voice_assistant.storage.speakers import create_speaker, load_speakers, save_speaker


def test_load_speakers_reads_front_matter(tmp_path: Path) -> None:
    pcs = tmp_path / "pcs"
    pcs.mkdir()
    (pcs / "valen.md").write_text(
        "---\nname: Valen\naffiliations:\n- lantern\nactive: true\n---\n\nA wandering bard.\n",
        encoding="utf-8",
    )
    speakers = load_speakers(tmp_path)
    assert len(speakers) == 1
    speaker = speakers[0]
    assert speaker.id == "valen"
    assert speaker.name == "Valen"
    assert speaker.active is True
    assert speaker.affiliations == ("lantern",)
    assert speaker.profile == "A wandering bard."


def test_load_speakers_empty_when_no_pcs_dir(tmp_path: Path) -> None:
    assert load_speakers(tmp_path) == ()


def test_create_speaker_and_save(tmp_path: Path) -> None:
    speaker = create_speaker(tmp_path, "new hero", "New Hero")
    assert speaker.id == "new-hero"
    assert (tmp_path / "pcs" / "new-hero.md").exists()
    updated = speaker.model_copy(update={"profile": "A brave adventurer.", "active": True})
    save_speaker(tmp_path, updated)
    speakers = load_speakers(tmp_path)
    assert len(speakers) == 1
    assert speakers[0].active is True
    assert speakers[0].profile == "A brave adventurer."


def test_create_speaker_rejects_existing(tmp_path: Path) -> None:
    create_speaker(tmp_path, "hero", "Hero")
    with pytest.raises(CampaignError, match="already exists"):
        create_speaker(tmp_path, "hero", "Hero")
