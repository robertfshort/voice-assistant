from __future__ import annotations

import asyncio
import re
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.domain.models import VoiceConfig, VoiceProviderConfig
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
from voice_assistant.services.text_to_speech import speak_text
from voice_assistant.storage.credentials import CredentialStore
from voice_assistant.storage.npc_creation import NpcDraft
from voice_assistant.storage.voices import load_voice_registry


class NpcDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        credentials: CredentialStore | None = None,
        draft: NpcDraft | None = None,
        voice_base_directory: str = ".",
        voice_root: Path | None = None,
        default_voice_provider: str = "gemini",
        output_device: str = "",
        output_latency: str = "low",
        output_blocksize: int = 0,
    ) -> None:
        super().__init__(parent)
        self._credentials = credentials or CredentialStore()
        self._voice_base_directory = voice_base_directory
        self._voice_root = voice_root
        self._default_voice_provider = default_voice_provider
        self._output_device = output_device
        self._output_latency = output_latency
        self._output_blocksize = output_blocksize
        self._pending_generations: dict[str, asyncio.Task[None]] = {}
        self._pending_expansion: asyncio.Task[None] | None = None
        self.setWindowTitle("Create NPC")
        self.resize(900, 680)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        identity_tab = QWidget()
        identity_form = QFormLayout(identity_tab)
        knowledge_tab = QWidget()
        knowledge_form = QFormLayout(knowledge_tab)
        details_tab = QWidget()
        details_form = QFormLayout(details_tab)
        voice_tab = QWidget()
        voice_form = QFormLayout(voice_tab)

        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self._suggest_id)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("lowercase-id-with-hyphens")
        self.role_input = QTextEdit()
        self.role_input.setMinimumHeight(110)
        self.personality_input = QTextEdit()
        self.personality_input.setMinimumHeight(110)
        self.background_input = QTextEdit()
        self.background_input.setMinimumHeight(110)
        self.goals_input = QTextEdit()
        self.goals_input.setMinimumHeight(100)
        self.public_knowledge_input = QTextEdit()
        self.public_knowledge_input.setMinimumHeight(100)
        self.affiliations_input = QTextEdit()
        self.affiliations_input.setMinimumHeight(100)
        self.affiliations_input.setToolTip(
            "One per line, or comma-separated. Used for restricted lore."
        )
        self.relationships_input = QTextEdit()
        self.relationships_input.setMinimumHeight(100)
        self.relationships_input.setToolTip("One per line, or comma-separated.")
        self.home_input = QLineEdit()
        self.home_input.setPlaceholderText("Where the NPC is from")
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Where the NPC is right now")
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
        self.voice_provider_input = QComboBox()
        self.voice_provider_input.addItems(("gemini", "piper"))
        self.voice_gender_input = QComboBox()
        self.voice_gender_input.addItems(GEMINI_GENDERS)
        self.voice_input = QComboBox()
        self.piper_voice_input = QComboBox()
        self.piper_voice_input.setEditable(True)
        self.piper_voice_input.setPlaceholderText("Name from voices.yaml")
        self._refresh_piper_voices()
        self.piper_model_input = QLineEdit()
        self.piper_model_button = QPushButton("Browse…")
        self.piper_model_button.clicked.connect(self._browse_piper_model)
        self.piper_config_input = QLineEdit()
        self.piper_config_button = QPushButton("Browse…")
        self.piper_config_button.clicked.connect(self._browse_piper_config)
        self.piper_speaker_input = QSpinBox()
        self.piper_speaker_input.setRange(-1, 999)
        self.piper_speaker_input.setSpecialValueText("Default")
        self.piper_speaker_input.setValue(-1)
        self.piper_length_input = QDoubleSpinBox()
        self.piper_length_input.setRange(0.1, 5.0)
        self.piper_length_input.setValue(1.0)
        self.piper_length_input.setSingleStep(0.05)
        self.piper_noise_input = QDoubleSpinBox()
        self.piper_noise_input.setRange(0.0, 2.0)
        self.piper_noise_input.setValue(0.667)
        self.piper_noise_input.setSingleStep(0.05)
        self.piper_noise_w_input = QDoubleSpinBox()
        self.piper_noise_w_input.setRange(0.0, 2.0)
        self.piper_noise_w_input.setValue(0.8)
        self.piper_noise_w_input.setSingleStep(0.05)
        self.piper_silence_input = QDoubleSpinBox()
        self.piper_silence_input.setRange(0.0, 5.0)
        self.piper_silence_input.setSingleStep(0.1)
        self.piper_silence_input.setSuffix(" seconds")
        self.piper_sample_rate_input = QSpinBox()
        self.piper_sample_rate_input.setRange(0, 192000)
        self.piper_sample_rate_input.setSpecialValueText("Automatic")
        self.piper_sample_rate_input.setSingleStep(1000)
        self.piper_channels_input = QSpinBox()
        self.piper_channels_input.setRange(0, 2)
        self.piper_channels_input.setSpecialValueText("Automatic")

        identity_form.addRow("Name", self._field_with_ai(self.name_input, "name"))
        identity_form.addRow("Stable ID", self.id_input)
        identity_form.addRow("Role", self._field_with_ai(self.role_input, "role", flesh_out=True))
        identity_form.addRow(
            "Personality",
            self._field_with_ai(self.personality_input, "personality", flesh_out=True),
        )
        identity_form.addRow(
            "Background",
            self._field_with_ai(self.background_input, "background", flesh_out=True),
        )
        knowledge_form.addRow(
            "Goals", self._field_with_ai(self.goals_input, "goals", flesh_out=True)
        )
        knowledge_form.addRow(
            "Public knowledge",
            self._field_with_ai(self.public_knowledge_input, "public_knowledge", flesh_out=True),
        )
        knowledge_form.addRow("Affiliations", self.affiliations_input)
        knowledge_form.addRow("Relationships", self.relationships_input)

        details_form.addRow("Home region", self.home_input)
        details_form.addRow("Current location", self.location_input)
        voice_form.addRow("Mood", self._field_with_ai(self.mood_input, "mood"))
        voice_form.addRow(
            "Speaking style", self._field_with_ai(self.style_input, "speaking_style")
        )
        voice_form.addRow("Preferred TTS", self.voice_provider_input)
        voice_form.addRow("Voice gender", self.voice_gender_input)
        voice_form.addRow("Gemini voice", self._field_with_ai(self.voice_input, "gemini_voice"))
        voice_form.addRow("Piper registered voice", self.piper_voice_input)
        voice_form.addRow(
            "Piper model", self._path_field(self.piper_model_input, self.piper_model_button)
        )
        voice_form.addRow(
            "Piper config", self._path_field(self.piper_config_input, self.piper_config_button)
        )
        voice_form.addRow("Piper speaker", self.piper_speaker_input)
        voice_form.addRow("Piper length scale", self.piper_length_input)
        voice_form.addRow("Piper noise scale", self.piper_noise_input)
        voice_form.addRow("Piper noise width", self.piper_noise_w_input)
        voice_form.addRow("Piper sentence silence", self.piper_silence_input)
        voice_form.addRow("Piper output rate", self.piper_sample_rate_input)
        voice_form.addRow("Piper output channels", self.piper_channels_input)

        self.portrait_input = QLineEdit()
        self.portrait_input.setReadOnly(True)
        self.portrait_browse_button = QPushButton("Browse…")
        self.portrait_browse_button.clicked.connect(self._browse_portrait)
        self.portrait_preview = QLabel()
        self.portrait_preview.setFixedSize(96, 96)
        self.portrait_preview.setScaledContents(True)
        self.portrait_preview.setStyleSheet("border: 1px solid gray;")
        portrait_layout = QHBoxLayout()
        portrait_layout.addWidget(self.portrait_input, 1)
        portrait_layout.addWidget(self.portrait_browse_button)
        portrait_layout.addWidget(self.portrait_preview)
        details_form.addRow("Portrait", portrait_layout)

        self.archived_input = QCheckBox("Archived (hide from active NPC list)")
        details_form.addRow(self.archived_input)

        self.tabs.addTab(identity_tab, "Identity")
        self.tabs.addTab(knowledge_tab, "Knowledge")
        self.tabs.addTab(details_tab, "Details")
        self.tabs.addTab(voice_tab, "Voice")
        layout.addWidget(self.tabs, 1)

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
            self.voice_provider_input.setCurrentText(self._default_voice_provider)
            self._set_voice("Aoede")

    def _apply_draft(self, draft: NpcDraft) -> None:
        self.name_input.setText(draft.name)
        self.id_input.setText(draft.id)
        self.role_input.setPlainText(draft.role)
        self.personality_input.setPlainText(draft.personality)
        self.background_input.setPlainText(draft.background)
        self.goals_input.setPlainText(draft.goals)
        self.public_knowledge_input.setPlainText(draft.public_knowledge)
        self.affiliations_input.setPlainText(draft.affiliations)
        self.home_input.setText(draft.home)
        self.location_input.setText(draft.location)
        self.relationships_input.setPlainText(draft.relationships)
        self.mood_input.setCurrentText(draft.mood)
        self.style_input.setCurrentText(draft.speaking_style)
        self.voice_provider_input.setCurrentText(draft.preferred_voice_provider)
        self._set_voice(draft.gemini_voice)
        self.piper_voice_input.setCurrentText(draft.piper_voice)
        self.piper_model_input.setText(draft.piper_model)
        self.piper_config_input.setText(draft.piper_config)
        self.piper_speaker_input.setValue(
            draft.piper_speaker_id if draft.piper_speaker_id is not None else -1
        )
        self.piper_length_input.setValue(draft.piper_length_scale)
        self.piper_noise_input.setValue(draft.piper_noise_scale)
        self.piper_noise_w_input.setValue(draft.piper_noise_w)
        self.piper_silence_input.setValue(draft.piper_sentence_silence)
        self.piper_sample_rate_input.setValue(draft.piper_sample_rate)
        self.piper_channels_input.setValue(draft.piper_channels)
        if draft.portrait:
            self.portrait_input.setText(draft.portrait)
            self._load_portrait_preview(draft.portrait)
        self.archived_input.setChecked(draft.archived)

    def _refresh_piper_voices(self) -> None:
        registry = load_voice_registry(self._voice_root)
        names = sorted(registry.piper.keys())
        current = self.piper_voice_input.currentText()
        self.piper_voice_input.blockSignals(True)
        self.piper_voice_input.clear()
        self.piper_voice_input.addItem("")
        self.piper_voice_input.addItems(names)
        if self.piper_voice_input.findText(current) >= 0:
            self.piper_voice_input.setCurrentText(current)
        else:
            self.piper_voice_input.setEditText(current)
        self.piper_voice_input.blockSignals(False)

    def _path_field(self, field: QLineEdit, button: QPushButton) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return container

    def _browse_piper_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Piper model", "", "ONNX (*.onnx)")
        if path:
            self.piper_model_input.setText(path)
            default_config = f"{path}.json"
            if not self.piper_config_input.text() and Path(default_config).is_file():
                self.piper_config_input.setText(default_config)

    def _browse_piper_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Piper config", "", "JSON (*.json)")
        if path:
            self.piper_config_input.setText(path)

    def _browse_portrait(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select portrait image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            self.portrait_input.setText(path)
            self._load_portrait_preview(path)

    def _load_portrait_preview(self, path: str) -> None:
        if not path:
            self.portrait_preview.clear()
            return
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.portrait_preview.setPixmap(pixmap)
        else:
            self.portrait_preview.clear()

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
        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        generate_button = QPushButton("Generate with AI")
        generate_button.clicked.connect(
            lambda: self._start_field_generation(field, generate_button, flesh_out=False)
        )
        actions.addWidget(generate_button)
        if flesh_out:
            flesh_button = QPushButton("Flesh out with AI")
            flesh_button.clicked.connect(
                lambda: self._start_field_generation(field, flesh_button, flesh_out=True)
            )
            actions.addWidget(flesh_button)
        actions.addStretch()
        layout.addLayout(actions)
        return container

    def _existing_fields(self) -> dict[str, str]:
        return {
            "name": self.name_input.text().strip(),
            "role": self.role_input.toPlainText().strip(),
            "personality": self.personality_input.toPlainText().strip(),
            "background": self.background_input.toPlainText().strip(),
            "goals": self.goals_input.toPlainText().strip(),
            "public_knowledge": self.public_knowledge_input.toPlainText().strip(),
            "affiliations": self.affiliations_input.toPlainText().strip(),
            "mood": self.mood_input.currentText().strip(),
            "speaking_style": self.style_input.currentText().strip(),
            "gemini_voice": self.voice_input.currentText(),
        }

    def _start_voice_preview(self) -> None:
        api_key = ""
        if self.voice_provider_input.currentText() == "gemini":
            try:
                api_key = self._credentials.get_gemini_api_key() or ""
            except ValueError as exc:
                QMessageBox.critical(self, "Credential error", str(exc))
                return
        self.voice_preview_button.setEnabled(False)
        self.voice_preview_button.setText("Playing preview…")
        asyncio.create_task(self._preview_voice(api_key))

    async def _preview_voice(self, api_key: str) -> None:
        name = self.name_input.text().strip() or "this character"
        try:
            piper = VoiceProviderConfig(
                voice=self.piper_voice_input.currentText().strip(),
                model=self.piper_model_input.text().strip(),
                config=self.piper_config_input.text().strip(),
                speaker_id=(
                    self.piper_speaker_input.value()
                    if self.piper_speaker_input.value() >= 0
                    else None
                ),
                length_scale=self.piper_length_input.value(),
                noise_scale=self.piper_noise_input.value(),
                noise_w=self.piper_noise_w_input.value(),
                sentence_silence=self.piper_silence_input.value(),
                sample_rate=self.piper_sample_rate_input.value(),
                channels=self.piper_channels_input.value(),
            )
            voice = VoiceConfig(
                style=self.style_input.currentText().strip(),
                preferred_provider=self.voice_provider_input.currentText(),
                providers={
                    "gemini": VoiceProviderConfig(voice=self.voice_input.currentText()),
                    "piper": piper,
                },
            )
            await speak_text(
                voice,
                f"[[{self.mood_input.currentText().strip()}]] Greetings. I am {name}. "
                "This is how I will sound at the table.",
                base_directory=Path(self._voice_base_directory),
                api_key=api_key,
                voice_root=self._voice_root,
                output_device=self._output_device,
                output_latency=self._output_latency,
                output_blocksize=self._output_blocksize,
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
        existing = self._pending_generations.get(field)
        if existing is not None and not existing.done():
            existing.cancel()
        task = asyncio.create_task(
            self._generate_field(api_key, field, button, original_label, flesh_out=flesh_out)
        )
        self._pending_generations[field] = task

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
            self._pending_generations.pop(field, None)

    def _set_field(self, field: str, value: str) -> None:
        text_fields = {
            "name": self.name_input,
            "role": self.role_input,
            "personality": self.personality_input,
            "background": self.background_input,
            "goals": self.goals_input,
            "public_knowledge": self.public_knowledge_input,
            "affiliations": self.affiliations_input,
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
        if self._pending_expansion is not None and not self._pending_expansion.done():
            self._pending_expansion.cancel()
        self._pending_expansion = asyncio.create_task(self._expand_with_ai(api_key))

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
            self._pending_expansion = None

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
            affiliations=self.affiliations_input.toPlainText().strip(),
            relationships=self.relationships_input.toPlainText().strip(),
            home=self.home_input.text().strip(),
            location=self.location_input.text().strip(),
            mood=self.mood_input.currentText().strip(),
            speaking_style=self.style_input.currentText().strip(),
            preferred_voice_provider=self.voice_provider_input.currentText(),
            gemini_voice=self.voice_input.currentText(),
            piper_voice=self.piper_voice_input.currentText().strip(),
            piper_model=self.piper_model_input.text().strip(),
            piper_config=self.piper_config_input.text().strip(),
            piper_speaker_id=(
                self.piper_speaker_input.value() if self.piper_speaker_input.value() >= 0 else None
            ),
            piper_length_scale=self.piper_length_input.value(),
            piper_noise_scale=self.piper_noise_input.value(),
            piper_noise_w=self.piper_noise_w_input.value(),
            piper_sentence_silence=self.piper_silence_input.value(),
            piper_sample_rate=self.piper_sample_rate_input.value(),
            piper_channels=self.piper_channels_input.value(),
            portrait=self.portrait_input.text().strip() or None,
            archived=self.archived_input.isChecked(),
        )
