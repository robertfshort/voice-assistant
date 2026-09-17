from pytestqt.qtbot import QtBot

from voice_assistant.ui.session_transcription_dialog import SessionTranscriptionReviewDialog


def test_review_dialog_returns_selected_speaker_and_edited_text(qtbot: QtBot) -> None:
    dialog = SessionTranscriptionReviewDialog("Hello world", ["gm", "Player 1"])
    qtbot.addWidget(dialog)
    dialog._text_edit.setPlainText("Hello there")
    dialog._speaker_input.setCurrentText("gm")

    assert dialog.speaker() == "gm"
    assert dialog.transcript() == "Hello there"


def test_review_dialog_allows_typed_speaker(qtbot: QtBot) -> None:
    dialog = SessionTranscriptionReviewDialog("Hello world", ["gm"])
    qtbot.addWidget(dialog)
    dialog._speaker_input.setCurrentText("Player 2")

    assert dialog.speaker() == "Player 2"
