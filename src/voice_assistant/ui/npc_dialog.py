from __future__ import annotations

import asyncio
import re

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.services.gemini_voices import (
    GEMINI_GENDERS,
    gender_for_voice,
    voices_for_gender,
)
from voice_assistant.services.npc_generation import (
    NpcExpansion,
    expand_npc,
    generate_npc_field,
)
from voice_assistant.services.voice_preview import preview_voice
from voice_assistant.storage.credentials import CredentialStore
from voice_assistant.storage.npc_creation import NpcDraft


class NpcDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        credentials: CredentialStore | None = None,
        draft: NpcDraft | None = None,
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
        self.voice_gender_input = QComboBox()
        self.voice_gender_input.addItems(GEMINI_GENDERS)
        self.voice_input = QComboBox()

        form.addRow("Name", self._field_with_ai(self.name_input, "name"))
        form.addRow("Stable ID", self.id_input)
        form.addRow("Role", self._field_with_ai(self.role_input, "role", flesh_out=True))
        form.addRow(
            "Personality",
            self._field_with_ai(self.personality_input, "personality", flesh_out=True),
        )
        form.addRow(
            "Background", self._field_with_ai(self.background_input, "background", flesh_out=True)
        )
        form.addRow("Goals", self._field_with_ai(self.goals_input, "goals", flesh_out=True))
        form.addRow(
            "Public knowledge",
            self._field_with_ai(self.public_knowledge_input, "public_knowledge", flesh_out=True),
        )
        form.addRow("Mood", self._field_with_ai(self.mood_input, "mood"))
        form.addRow("Speaking style", self._field_with_ai(self.style_input, "speaking_style"))
        form.addRow("Voice gender", self.voice_gender_input)
        form.addRow("Gemini voice", self._field_with_ai(self.voice_input, "gemini_voice"))
        layout.addLayout(form)

        action_row = QHBoxLayout()
        self.ai_expand_button = QPushButton("Generate this NPC with AI")
        self.ai_expand_button.clicked.connect(self._start_ai_expansion)
        action_row.addWidget(self.ai_expand_button)
        self.voice_preview_button = QPushButton("Test voice settings")
        self.voice_preview_button.clicked.connect(self._start_voice_preview)
        action_row.addWidget(self.voice_preview_button)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.voice_gender_input.currentTextChanged.connect(self._on_gender_changed)
        self.voice_input.currentTextChanged.connect(self._on_voice_changed)
        if draft is not None:
            self.setWindowTitle("Edit NPC")
            self._apply_draft(draft)
            self.id_input.setEnabled(False)
        else:
            self._set_voice("Aoede")

    def _apply_draft(self, draft: NpcDraft) -> None:
        self.name_input.setText(draft.name)
        self.id_input.setText(draft.id)
        self.role_input.setPlainText(draft.role)
        self.personality_input.setPlainText(draft.personality)
        self.background_input.setPlainText(draft.background)
        self.goals_input.setPlainText(draft.goals)
        self.public_knowledge_input.setPlainText(draft.public_knowledge)
        self.mood_input.setCurrentText(draft.mood)
        self.style_input.setCurrentText(draft.speaking_style)
        self._set_voice(draft.gemini_voice)

    def _on_gender_changed(self) -> None:
        gender = self.voice_gender_input.currentText()
        voices = voices_for_gender(gender)
        current_voice = self.voice_input.currentText()
        self.voice_input.blockSignals(True)
        self.voice_input.clear()
        self.voice_input.addItems(voices)
        new_voice = current_voice if current_voice in voices else voices[0]
        self.voice_input.setCurrentText(new_voice)
        self.voice_input.blockSignals(False)

    def _on_voice_changed(self) -> None:
        voice = self.voice_input.currentText()
        if not voice:
            return
        gender = gender_for_voice(voice)
        if gender != self.voice_gender_input.currentText():
            self.voice_gender_input.blockSignals(True)
            self.voice_gender_input.setCurrentText(gender)
            self.voice_gender_input.blockSignals(False)
            voices = voices_for_gender(gender)
            if voice in voices:
                self.voice_input.blockSignals(True)
                self.voice_input.clear()
                self.voice_input.addItems(voices)
                self.voice_input.setCurrentText(voice)
                self.voice_input.blockSignals(False)

    def _set_voice(self, voice: str) -> None:
        gender = gender_for_voice(voice)
        self.voice_gender_input.blockSignals(True)
        self.voice_gender_input.setCurrentText(gender)
        self.voice_gender_input.blockSignals(False)
        self.voice_input.blockSignals(True)
        self.voice_input.clear()
        self.voice_input.addItems(voices_for_gender(gender))
        if self.voice_input.findText(voice) < 0:
            self.voice_input.addItem(voice)
        self.voice_input.setCurrentText(voice)
        self.voice_input.blockSignals(False)

    def _field_with_ai(
        self, field_widget: QWidget, field: str, *, flesh_out: bool = False
    ) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field_widget, 1)
        generate_button = QPushButton("Generate with AI")
        generate_button.clicked.connect(
            lambda: self._start_field_generation(field, generate_button, flesh_out=False)
        )
        layout.addWidget(generate_button)
        if flesh_out:
            flesh_button = QPushButton("Flesh out with AI")
            flesh_button.clicked.connect(
                lambda: self._start_field_generation(field, flesh_button, flesh_out=True)
            )
            layout.addWidget(flesh_button)
        return container

    def _existing_fields(self) -> dict[str, str]:
        return {
            "name": self.name_input.text().strip(),
            "role": self.role_input.toPlainText().strip(),
            "personality": self.personality_input.toPlainText().strip(),
            "background": self.background_input.toPlainText().strip(),
            "goals": self.goals_input.toPlainText().strip(),
            "public_knowledge": self.public_knowledge_input.toPlainText().strip(),
            "mood": self.mood_input.currentText().strip(),
            "speaking_style": self.style_input.currentText().strip(),
            "gemini_voice": self.voice_input.currentText(),
        }

    def _start_voice_preview(self) -> None:
        try:
            api_key = self._credentials.get_gemini_api_key()
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        if not api_key:
            QMessageBox.information(
                self,
                "Gemini API key required",
                "Store a Gemini API key from the main window before testing a voice.",
            )
            return
        self.voice_preview_button.setEnabled(False)
        self.voice_preview_button.setText("Playing preview…")
        asyncio.create_task(self._preview_voice(api_key))

    async def _preview_voice(self, api_key: str) -> None:
        name = self.name_input.text().strip() or "this character"
        try:
            await preview_voice(
                api_key,
                self.voice_input.currentText(),
                self.mood_input.currentText().strip(),
                self.style_input.currentText().strip(),
                text=f"Greetings. I am {name}. This is how I will sound at the table.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Voice preview error", str(exc))
        finally:
            self.voice_preview_button.setEnabled(True)
            self.voice_preview_button.setText("Test voice settings")

    def _start_field_generation(self, field: str, button: QPushButton, *, flesh_out: bool) -> None:
        try:
            api_key = self._credentials.get_gemini_api_key()
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        if not api_key:
            QMessageBox.information(
                self,
                "Gemini API key required",
                "Store a Gemini API key from the main window before using AI generation.",
            )
            return
        button.setEnabled(False)
        original_label = button.text()
        button.setText("Generating…")
        asyncio.create_task(
            self._generate_field(api_key, field, button, original_label, flesh_out=flesh_out)
        )

    async def _generate_field(
        self,
        api_key: str,
        field: str,
        button: QPushButton,
        original_label: str,
        *,
        flesh_out: bool,
    ) -> None:
        try:
            value = await generate_npc_field(
                api_key, field, self._existing_fields(), flesh_out=flesh_out
            )
            self._set_field(field, value)
        except Exception as exc:
            QMessageBox.critical(self, "NPC generation error", str(exc))
        finally:
            button.setEnabled(True)
            button.setText(original_label)

    def _set_field(self, field: str, value: str) -> None:
        text_fields = {
            "name": self.name_input,
            "role": self.role_input,
            "personality": self.personality_input,
            "background": self.background_input,
            "goals": self.goals_input,
            "public_knowledge": self.public_knowledge_input,
        }
        widget = text_fields.get(field)
        if isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(value)
        elif field == "mood":
            self.mood_input.setCurrentText(value)
        elif field == "speaking_style":
            self.style_input.setCurrentText(value)
        elif field == "gemini_voice":
            self._set_voice(value)

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
        try:
            expansion = await expand_npc(api_key, self._existing_fields())
        except Exception as exc:
            QMessageBox.critical(self, "NPC generation error", str(exc))
        else:
            preview = (
                f"Name\n{expansion.name}\n\nRole\n{expansion.role}\n\n"
                f"Personality\n{expansion.personality}\n\n"
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
            self.ai_expand_button.setText("Generate this NPC with AI")

    def _apply_expansion(self, expansion: NpcExpansion) -> None:
        self.name_input.setText(expansion.name)
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
