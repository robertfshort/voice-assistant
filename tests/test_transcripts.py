from pathlib import Path

from voice_assistant.storage.transcripts import (
    append_transcript,
    clear_transcript,
    load_transcript,
)


def test_transcripts_are_isolated_by_npc(tmp_path: Path) -> None:
    append_transcript(tmp_path, "elara", "player", "Hello")
    append_transcript(tmp_path, "rell", "npc", "State your business")

    assert [entry.text for entry in load_transcript(tmp_path, "elara")] == ["Hello"]
    assert [entry.text for entry in load_transcript(tmp_path, "rell")] == ["State your business"]


def test_private_gm_entries_are_marked(tmp_path: Path) -> None:
    append_transcript(tmp_path, "elara", "gm", "Become suspicious", private=True)

    entry = load_transcript(tmp_path, "elara")[0]
    assert entry.private is True
    assert entry.speaker == "gm"


def test_clear_transcript_only_removes_selected_npc(tmp_path: Path) -> None:
    append_transcript(tmp_path, "elara", "player", "Hello")
    append_transcript(tmp_path, "rell", "npc", "State your business")

    clear_transcript(tmp_path, "elara")

    assert load_transcript(tmp_path, "elara") == ()
    assert [entry.text for entry in load_transcript(tmp_path, "rell")] == [
        "State your business"
    ]
