import shutil
from pathlib import Path

from PySide6.QtWidgets import QDialog
from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

from voice_assistant.storage.npc_creation import NpcDraft
from voice_assistant.storage.transcripts import append_transcript
from voice_assistant.ui import main_window as main_window_module
from voice_assistant.ui.main_window import MainWindow

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_main_window_loads_sample_campaign(qtbot: QtBot) -> None:
    window = MainWindow(REPOSITORY_ROOT / "examples" / "campaigns")
    qtbot.addWidget(window)

    assert window.windowTitle() == "RPG Voice Assistant"
    assert window._campaign_list.count() == 1
    assert window._npc_list.count() >= 2
    assert window._npc_heading.text() == "Elara Voss"
    assert window._start_button.isEnabled()


def test_create_npc_dialog_result_reloads_and_selects_character(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    draft = NpcDraft(
        id="guildmaster-vale",
        name="Guildmaster Vale",
        role="Leader of the merchants guild.",
        personality="Patient and exacting.",
        mood="confident",
        speaking_style="measured",
        gemini_voice="Charon",
    )

    class AcceptedNpcDialog:
        def __init__(self, parent: MainWindow, **kwargs: object) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def draft(self) -> NpcDraft:
            return draft

    monkeypatch.setattr(main_window_module, "NpcDialog", AcceptedNpcDialog)
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "question",
        lambda *a, **k: main_window_module.QMessageBox.StandardButton.No,
    )
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)
    initial_count = window._npc_list.count()

    window._create_npc()

    assert window._npc_list.count() == initial_count + 1
    assert window._npc_heading.text() == "Guildmaster Vale"
    assert window._active_npc is not None
    assert window._active_npc.id == "guildmaster-vale"
    assert (campaign_root / "sample" / "characters" / "guildmaster-vale").is_dir()


def test_duplicate_npc_creates_a_copy(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    source = NpcDraft(
        id="elara-copy",
        name="Copy of Elara Voss",
        role="Tavern keeper",
        personality="Guarded",
        gemini_voice="Aoede",
    )

    class DuplicateDialog:
        def __init__(
            self,
            parent: object,
            *,
            credentials: object,
            draft: NpcDraft,
            voice_base_directory: str,
        ) -> None:
            pass

        def setWindowTitle(self, title: str) -> None:  # noqa: N802
            pass

        id_input = type("Input", (), {"setEnabled": lambda self, *args: None})

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def draft(self) -> NpcDraft:
            return source

    monkeypatch.setattr(
        main_window_module.QInputDialog, "getText", lambda *a, **k: ("elara-copy", True)
    )
    monkeypatch.setattr(main_window_module, "NpcDialog", DuplicateDialog)
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)
    initial_count = window._npc_list.count()

    window._duplicate_npc()

    assert window._npc_list.count() == initial_count + 1
    assert (campaign_root / "sample" / "characters" / "elara-copy").is_dir()
    assert window._active_npc is not None
    assert window._active_npc.id == "elara-copy"


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


def test_npc_knowledge_can_be_edited_and_appended_without_crossing_npcs(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(
        main_window_module.QInputDialog, "getText", lambda *a, **k: ("Updated memory", True)
    )
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)

    assert window._knowledge_heading.text() == "Elara Voss"
    assert window._knowledge_editor.toPlainText().startswith("# Elara Voss")
    window._knowledge_editor.append("\nEdited knowledge.")
    window._save_npc_knowledge()
    window._knowledge_append.setPlainText("Appended knowledge.")
    window._append_npc_knowledge()

    elara_memory = (
        campaign_root / "sample" / "characters" / "elara-voss" / "memory.md"
    ).read_text(encoding="utf-8")
    rell_memory = (
        campaign_root / "sample" / "characters" / "captain-rell" / "memory.md"
    ).read_text(encoding="utf-8")
    assert "Edited knowledge." in elara_memory
    assert "Appended knowledge." in elara_memory
    assert "Edited knowledge." not in rell_memory
    assert "Appended knowledge." not in rell_memory


def test_lore_entry_can_be_created_and_selected(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    monkeypatch.setattr(
        main_window_module.QInputDialog,
        "getText",
        lambda *args, **kwargs: ("places/three-roads.md", True),
    )
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)

    window._create_lore()

    created = campaign_root / "sample" / "lore" / "places" / "three-roads.md"
    assert created.read_text(encoding="utf-8") == "# Three Roads\n\n"
    assert window._active_lore_id == "places/three-roads.md"
    assert window._lore_editor.toPlainText() == "# Three Roads\n\n"


def test_lore_can_be_viewed_and_saved(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(
        main_window_module.QInputDialog, "getText", lambda *a, **k: ("Added fact", True)
    )
    campaign_root = tmp_path / "campaigns"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "campaigns", campaign_root)
    window = MainWindow(campaign_root)
    qtbot.addWidget(window)

    assert window._lore_list.count() == 1
    assert window._lore_list.currentItem().text() == "lanterns-rest.md"
    assert "Lantern's Rest" in window._lore_editor.toPlainText()

    window._lore_editor.append("\nA newly established fact.")
    window._save_lore()

    saved = campaign_root / "sample" / "lore" / "lanterns-rest.md"
    assert "A newly established fact." in saved.read_text(encoding="utf-8")
    assert window._active_campaign is not None
    assert "A newly established fact." in window._active_campaign.lore["lanterns-rest.md"]


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
