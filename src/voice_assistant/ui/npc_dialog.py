from __future__ import annotations

import asyncio
import re

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.services.npc_generation import NpcExpansion, expand_npc
from voice_assistant.storage.credentials import CredentialStore
from voice_assistant.storage.npc_creation import NpcDraft


class NpcDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, *, credentials: CredentialStore | None = None
    ) -> None:
        super().__init__(parent)
        self._credentials = credentials or CredentialStore()
        self.setWindowTitle("Create NPC")
        self.resize(620, 760)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self._suggest_id)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("lowercase-id-with-hyphens")
        self.role_input = QTextEdit()
        self.role_input.setMaximumHeight(90)
        self.personality_input = QTextEdit()
        self.personality_input.setMaximumHeight(80)
        self.background_input = QTextEdit()
        self.background_input.setMaximumHeight(80)
        self.goals_input = QTextEdit()
        self.goals_input.setMaximumHeight(80)
        self.public_knowledge_input = QTextEdit()
        self.public_knowledge_input.setMaximumHeight(80)
        self.mood_input = QComboBox()
        self.mood_input.setEditable(True)
        self.mood_input.addItems(
            ("neutral", "warm", "guarded", "cheerful", "somber", "tense", "authoritative")
        )
        self.style_input = QComboBox()
        self.style_input.setEditable(True)
        self.style_input.addItems(
            ("natural", "measured", "conversational", "formal", "terse", "animated")
        )
        self.voice_input = QComboBox()
        self.voice_input.addItems(
            ("Aoede", "Charon", "Fenrir", "Kore", "Leda", "Orus", "Puck", "Zephyr")
        )

        form.addRow("Name", self.name_input)
        form.addRow("Stable ID", self.id_input)
        form.addRow("Role", self.role_input)
        form.addRow("Personality", self.personality_input)
        form.addRow("Background", self.background_input)
        form.addRow("Goals", self.goals_input)
        form.addRow("Public knowledge", self.public_knowledge_input)
        form.addRow("Mood", self.mood_input)
        form.addRow("Speaking style", self.style_input)
        form.addRow("Gemini voice", self.voice_input)
        layout.addLayout(form)

        self.ai_expand_button = QPushButton("Generate or expand with AI")
        self.ai_expand_button.clicked.connect(self._start_ai_expansion)
        layout.addWidget(self.ai_expand_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _suggest_id(self, name: str) -> None:
        if self.id_input.isModified():
            return
        suggestion = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        self.id_input.setText(suggestion)

    def _start_ai_expansion(self) -> None:
        try:
            api_key = self._credentials.get_gemini_api_key()
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        if not api_key:
            QMessageBox.information(
                self,
                "Gemini API key required",
                "Store a Gemini API key from the main window before using AI expansion.",
            )
            return
        self.ai_expand_button.setEnabled(False)
        self.ai_expand_button.setText("Generating…")
        asyncio.create_task(self._expand_with_ai(api_key))

    async def _expand_with_ai(self, api_key: str) -> None:
        existing = {
            "name": self.name_input.text().strip(),
            "role": self.role_input.toPlainText().strip(),
            "personality": self.personality_input.toPlainText().strip(),
            "background": self.background_input.toPlainText().strip(),
            "goals": self.goals_input.toPlainText().strip(),
            "public_knowledge": self.public_knowledge_input.toPlainText().strip(),
            "mood": self.mood_input.currentText().strip(),
            "speaking_style": self.style_input.currentText().strip(),
        }
        try:
            expansion = await expand_npc(api_key, existing)
        except Exception as exc:
            QMessageBox.critical(self, "NPC generation error", str(exc))
        else:
            preview = (
                f"Role\n{expansion.role}\n\nPersonality\n{expansion.personality}\n\n"
                f"Background\n{expansion.background}\n\nGoals\n{expansion.goals}\n\n"
                f"Public knowledge\n{expansion.public_knowledge}\n\n"
                f"Mood\n{expansion.mood}\n\nSpeaking style\n{expansion.speaking_style}"
            )
            accepted = QMessageBox.question(
                self,
                "Apply generated NPC draft?",
                preview,
                QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
            )
            if accepted == QMessageBox.StandardButton.Apply:
                self._apply_expansion(expansion)
        finally:
            self.ai_expand_button.setEnabled(True)
            self.ai_expand_button.setText("Generate or expand with AI")

    def _apply_expansion(self, expansion: NpcExpansion) -> None:
        self.role_input.setPlainText(expansion.role)
        self.personality_input.setPlainText(expansion.personality)
        self.background_input.setPlainText(expansion.background)
        self.goals_input.setPlainText(expansion.goals)
        self.public_knowledge_input.setPlainText(expansion.public_knowledge)
        self.mood_input.setCurrentText(expansion.mood)
        self.style_input.setCurrentText(expansion.speaking_style)

    def draft(self) -> NpcDraft:
        return NpcDraft(
            id=self.id_input.text().strip(),
            name=self.name_input.text().strip(),
            role=self.role_input.toPlainText().strip(),
            personality=self.personality_input.toPlainText().strip(),
            background=self.background_input.toPlainText().strip(),
            goals=self.goals_input.toPlainText().strip(),
            public_knowledge=self.public_knowledge_input.toPlainText().strip(),
            mood=self.mood_input.currentText().strip(),
            speaking_style=self.style_input.currentText().strip(),
            gemini_voice=self.voice_input.currentText(),
        )
