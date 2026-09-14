from datetime import UTC, datetime

from voice_assistant.services.session_notes import SessionNotes, _format_transcript
from voice_assistant.storage.transcripts import TranscriptEntry


def test_format_transcript_excludes_private_entries() -> None:
    entries = (
        TranscriptEntry(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            speaker="player",
            text="Hello, Elara.",
            private=False,
        ),
        TranscriptEntry(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            speaker="gm",
            text="Secret directive.",
            private=True,
        ),
    )
    text = _format_transcript(entries)
    assert "Hello, Elara." in text
    assert "Secret directive." not in text


def test_session_notes_model_parsing() -> None:
    raw = (
        '{"summary": "The party met Elara.", '
        '"proposed_memory": "Elara greeted them warmly.", '
        '"proposed_lore": ["Elara is the tavernkeeper"]}'
    )
    notes = SessionNotes.model_validate_json(raw)
    assert notes.summary == "The party met Elara."
    assert notes.proposed_memory == "Elara greeted them warmly."
    assert notes.proposed_lore == ("Elara is the tavernkeeper",)
