import shutil
from pathlib import Path

from pytestqt.qtbot import QtBot

from voice_assistant.storage.transcripts import append_transcript
from voice_assistant.ui.main_window import MainWindow

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_main_window_loads_sample_campaign(qtbot: QtBot) -> None:
    window = MainWindow(REPOSITORY_ROOT / "examples" / "campaigns")
    qtbot.addWidget(window)

    assert window.windowTitle() == "RPG Voice Assistant"
    assert window._campaign_list.count() == 1
    assert window._npc_list.count() == 2
    assert window._npc_heading.text() == "Elara Voss"
    assert window._start_button.isEnabled()


def test_player_and_gm_inputs_are_visibly_distinct(qtbot: QtBot, tmp_path: Path) -> None:
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)

    window._player_input.setText("What happened to the caravan?")
    window._send_player_text()
    window._gm_input.setText("Become more suspicious.")
    window._send_gm_text()

    transcript = window._transcript.toPlainText()
    assert "Player: What happened to the caravan?" in transcript
    assert "GM instruction (private): Become more suspicious." in transcript


def test_switching_npcs_updates_profile_and_isolates_transcripts(
    qtbot: QtBot, tmp_path: Path
) -> None:
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    campaign_directory = campaign_root / "sample"
    append_transcript(campaign_directory, "elara-voss", "player", "Elara only")
    append_transcript(campaign_directory, "captain-rell", "player", "Rell only")
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)

    assert window._npc_heading.text() == "Elara Voss"
    assert "Elara only" in window._transcript.toPlainText()
    rell_row = next(
        row
        for row in range(window._npc_list.count())
        if window._npc_list.item(row).text() == "Captain Tomas Rell"
    )
    window._npc_list.setCurrentRow(rell_row)

    assert window._npc_heading.text() == "Captain Tomas Rell"
    assert "Captain of the Lantern's Rest road wardens" in window._profile.toPlainText()
    assert "Rell only" in window._transcript.toPlainText()
    assert "Elara only" not in window._transcript.toPlainText()
