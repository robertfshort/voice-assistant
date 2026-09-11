from pathlib import Path

from pytestqt.qtbot import QtBot

from voice_assistant.ui.main_window import MainWindow

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_main_window_loads_sample_campaign(qtbot: QtBot) -> None:
    window = MainWindow(REPOSITORY_ROOT / "examples" / "campaigns")
    qtbot.addWidget(window)

    assert window.windowTitle() == "RPG Voice Assistant"
    assert window._campaign_list.count() == 1
    assert window._npc_list.count() == 1
    assert window._npc_heading.text() == "Elara Voss"
    assert window._start_button.isEnabled()


def test_player_and_gm_inputs_are_visibly_distinct(qtbot: QtBot) -> None:
    window = MainWindow(REPOSITORY_ROOT / "examples" / "campaigns")
    qtbot.addWidget(window)

    window._player_input.setText("What happened to the caravan?")
    window._send_player_text()
    window._gm_input.setText("Become more suspicious.")
    window._send_gm_text()

    transcript = window._transcript.toPlainText()
    assert "Player: What happened to the caravan?" in transcript
    assert "GM instruction (private): Become more suspicious." in transcript
