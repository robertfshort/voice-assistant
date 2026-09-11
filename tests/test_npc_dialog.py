import asyncio

from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

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
    assert dialog.voice_input.currentText() == "Kore"


def test_voice_preview_uses_current_voice_mood_and_style(
    qtbot: QtBot, monkeypatch: MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    async def fake_preview(
        api_key: str, voice: str, mood: str, speaking_style: str, *, text: str
    ) -> None:
        captured.update(
            api_key=api_key,
            voice=voice,
            mood=mood,
            speaking_style=speaking_style,
            text=text,
        )

    monkeypatch.setattr(npc_dialog_module, "preview_voice", fake_preview)
    dialog = NpcDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("Mara Vale")
    dialog.voice_input.setCurrentText("Kore")
    dialog.mood_input.setCurrentText("warm")
    dialog.style_input.setCurrentText("measured")
    dialog.voice_preview_button.setEnabled(False)

    asyncio.run(dialog._preview_voice("test-key"))

    assert captured == {
        "api_key": "test-key",
        "voice": "Kore",
        "mood": "warm",
        "speaking_style": "measured",
        "text": "Greetings. I am Mara Vale. This is how I will sound at the table.",
    }
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
