from pytestqt.qtbot import QtBot

from voice_assistant.services.npc_generation import NpcExpansion
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


def test_field_generation_result_overwrites_only_selected_field(qtbot: QtBot) -> None:
    dialog = NpcDialog()
    qtbot.addWidget(dialog)
    dialog.role_input.setPlainText("Old role")
    dialog.personality_input.setPlainText("Keep this personality")

    dialog._set_field("role", "New role")

    assert dialog.role_input.toPlainText() == "New role"
    assert dialog.personality_input.toPlainText() == "Keep this personality"
