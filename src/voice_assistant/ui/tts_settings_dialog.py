from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.storage.settings import ProviderSettings, SpeechSettings


class TtsSettingsDialog(QDialog):
    def __init__(
        self,
        providers: ProviderSettings,
        speech: SpeechSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Text-to-speech settings")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.provider_input = QComboBox()
        self.provider_input.addItems(("gemini", "piper"))
        self.provider_input.setCurrentText(providers.speech)
        self.voice_root_input = QLineEdit(str(speech.voice_root or ""))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_voice_root)
        root_row = QHBoxLayout()
        root_row.addWidget(self.voice_root_input, 1)
        root_row.addWidget(browse)
        self.fallback_input = QLineEdit(", ".join(speech.fallback_order))
        self.fallback_input.setPlaceholderText("piper, gemini")
        form.addRow("Default provider", self.provider_input)
        form.addRow("Shared voices folder", root_row)
        form.addRow("Fallback order", self.fallback_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_voice_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Select shared voices folder", self.voice_root_input.text()
        )
        if selected:
            self.voice_root_input.setText(selected)

    def values(self) -> tuple[str, SpeechSettings]:
        root = self.voice_root_input.text().strip()
        fallback = tuple(
            item.strip().lower() for item in self.fallback_input.text().split(",") if item.strip()
        )
        return self.provider_input.currentText(), SpeechSettings(
            voice_root=Path(root) if root else None,
            fallback_order=fallback,
        )
