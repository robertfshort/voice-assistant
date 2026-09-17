import asyncio
from pathlib import Path

from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

from voice_assistant.domain.models import VoiceConfig
from voice_assistant.services.npc_generation import NpcExpansion
from voice_assistant.storage.npc_creation import NpcDraft
from voice_assistant.ui import npc_dialog as npc_dialog_module
from voice_assistant.ui.npc_dialog import NpcDialog


def test_whole_npc_expansion_applies_name_before_dependent_fields(qtbot: QtBot) -> None:
    dialog = NpcDialog()
    qtbot.addWidget(dialog)
    expansion = NpcExpansion(
        name="Mara Vale",
        role="Guildmaster",
        personality="Patient and exacting",
        background="A former caravan factor",
        goals="Protect regional trade",
        public_knowledge="The guild raised its dues",
        mood="confident",
        speaking_style="measured",
    )

    dialog._apply_expansion(expansion)

    assert dialog.name_input.text() == "Mara Vale"
    assert dialog.id_input.text() == "mara-vale"
    assert dialog.goals_input.toPlainText() == "Protect regional trade"
    assert dialog.public_knowledge_input.toPlainText() == "The guild raised its dues"


def test_piper_voice_is_editable_dropdown_of_registered_voices(
    qtbot: QtBot, tmp_path: Path
) -> None:
    (tmp_path / "voices.yaml").write_text(
        "piper:\n  innkeeper:\n    model: piper/innkeeper.onnx\n"
        "  sage:\n    model: piper/sage.onnx\n",
        encoding="utf-8",
    )
    dialog = NpcDialog(voice_root=tmp_path)
    qtbot.addWidget(dialog)
    items = [dialog.piper_voice_input.itemText(i) for i in range(dialog.piper_voice_input.count())]
    assert "" in items
    assert "innkeeper" in items
    assert "sage" in items


def test_editor_uses_tabs_with_room_for_multiline_fields(qtbot: QtBot) -> None:
    dialog = NpcDialog()
    qtbot.addWidget(dialog)

    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "Identity",
        "Knowledge",
        "Details",
        "Voice",
    ]
    assert dialog.role_input.minimumHeight() >= 100
    assert dialog.public_knowledge_input.minimumHeight() >= 100


def test_edit_dialog_prefills_fields_and_locks_stable_id(qtbot: QtBot) -> None:
    draft = NpcDraft(
        id="mara-vale",
        name="Mara Vale",
        role="Guildmaster",
        personality="Patient",
        gemini_voice="Kore",
    )
    dialog = NpcDialog(draft=draft)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Edit NPC"
    assert dialog.name_input.text() == "Mara Vale"
    assert dialog.id_input.text() == "mara-vale"
    assert not dialog.id_input.isEnabled()
    assert dialog.voice_gender_input.currentText() == "Female"
    assert dialog.voice_input.currentText() == "Kore"


def test_voice_gender_filter_populates_and_syncs(qtbot: QtBot) -> None:
    dialog = NpcDialog()
    qtbot.addWidget(dialog)

    assert dialog.voice_gender_input.currentText() == "Female"
    assert dialog.voice_input.count() == 14
    dialog._set_voice("Charon")

    assert dialog.voice_gender_input.currentText() == "Male"
    assert dialog.voice_input.currentText() == "Charon"
    assert "Kore" not in [
        dialog.voice_input.itemText(i) for i in range(dialog.voice_input.count())
    ]
    assert "Puck" in [dialog.voice_input.itemText(i) for i in range(dialog.voice_input.count())]


def test_voice_preview_uses_current_voice_mood_and_style(
    qtbot: QtBot, monkeypatch: MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    async def fake_speak(
        voice: object,
        text: str,
        *,
        base_directory: Path,
        api_key: str = "",
        voice_root: Path | None = None,
        output_device: str = "",
        output_latency: str = "low",
        output_blocksize: int = 0,
    ) -> None:
        captured.update(
            voice=voice,
            text=text,
            base_directory=base_directory,
            api_key=api_key,
        )

    monkeypatch.setattr(npc_dialog_module, "speak_text", fake_speak)
    dialog = NpcDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("Mara Vale")
    dialog._set_voice("Kore")
    dialog.mood_input.setCurrentText("warm")
    dialog.style_input.setCurrentText("measured")
    dialog.voice_preview_button.setEnabled(False)

    asyncio.run(dialog._preview_voice("test-key"))

    voice = captured["voice"]
    assert isinstance(voice, VoiceConfig)
    assert voice.preferred_provider == "gemini"
    assert voice.style == "measured"
    assert voice.providers["gemini"].voice == "Kore"
    assert captured["api_key"] == "test-key"
    assert captured["base_directory"] == Path(".")
    assert captured["text"] == (
        "[[warm]] Greetings. I am Mara Vale. This is how I will sound at the table."
    )
    assert dialog.voice_preview_button.isEnabled()
    assert dialog.voice_preview_button.text() == "Test voice settings"


def test_field_generation_result_overwrites_only_selected_field(qtbot: QtBot) -> None:
    dialog = NpcDialog()
    qtbot.addWidget(dialog)
    dialog.role_input.setPlainText("Old role")
    dialog.personality_input.setPlainText("Keep this personality")

    dialog._set_field("role", "New role")

    assert dialog.role_input.toPlainText() == "New role"
    assert dialog.personality_input.toPlainText() == "Keep this personality"
