from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.services.audio_devices import output_devices
from voice_assistant.storage.settings import ProviderSettings, SpeechSettings
from voice_assistant.storage.voices import import_piper_voice
from voice_assistant.ui.installed_voices_dialog import InstalledVoicesDialog
from voice_assistant.ui.piper_catalog_dialog import PiperCatalogDialog


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
        self.output_device_input = QComboBox()
        self.output_device_input.setEditable(True)
        self.output_device_input.addItem("Default", "")
        with suppress(Exception):
            for device_id, label in output_devices():
                self.output_device_input.addItem(label, device_id)
        selected_device = self.output_device_input.findData(speech.output_device)
        if selected_device >= 0:
            self.output_device_input.setCurrentIndex(selected_device)
        else:
            self.output_device_input.setCurrentText(speech.output_device)
        self.latency_input = QComboBox()
        self.latency_input.addItems(("low", "high"))
        self.latency_input.setCurrentText(speech.output_latency)
        self.blocksize_input = QSpinBox()
        self.blocksize_input.setRange(0, 65536)
        self.blocksize_input.setSpecialValueText("Automatic")
        self.blocksize_input.setValue(speech.output_blocksize)
        form.addRow("Default provider", self.provider_input)
        form.addRow("Shared voices folder", root_row)
        form.addRow("Fallback order", self.fallback_input)
        form.addRow("Output device", self.output_device_input)
        form.addRow("Output latency", self.latency_input)
        form.addRow("Output block size", self.blocksize_input)
        layout.addLayout(form)
        voice_buttons = QHBoxLayout()
        import_button = QPushButton("Import Piper voice…")
        import_button.clicked.connect(self._import_piper_voice)
        download_button = QPushButton("Download Piper voice…")
        download_button.clicked.connect(self._download_piper_voice)
        manage_button = QPushButton("Installed voices…")
        manage_button.clicked.connect(self._manage_piper_voices)
        voice_buttons.addWidget(import_button)
        voice_buttons.addWidget(download_button)
        voice_buttons.addWidget(manage_button)
        layout.addLayout(voice_buttons)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _manage_piper_voices(self) -> None:
        root_text = self.voice_root_input.text().strip()
        if not root_text:
            QMessageBox.information(
                self, "Shared voices folder required", "Choose a folder first."
            )
            return
        InstalledVoicesDialog(Path(root_text), self).exec()

    def _download_piper_voice(self) -> None:
        root_text = self.voice_root_input.text().strip()
        if not root_text:
            QMessageBox.information(
                self, "Shared voices folder required", "Choose a folder first."
            )
            return
        PiperCatalogDialog(Path(root_text), self).exec()

    def _import_piper_voice(self) -> None:
        root_text = self.voice_root_input.text().strip()
        if not root_text:
            QMessageBox.information(
                self, "Shared voices folder required", "Choose a folder first."
            )
            return
        name, accepted = QInputDialog.getText(
            self, "Import Piper voice", "Portable voice name (lowercase and hyphens)"
        )
        if not accepted or not name.strip():
            return
        model, _ = QFileDialog.getOpenFileName(self, "Select Piper model", "", "ONNX (*.onnx)")
        if not model:
            return
        default_config = f"{model}.json"
        config, _ = QFileDialog.getOpenFileName(
            self,
            "Select Piper config",
            default_config if Path(default_config).is_file() else "",
            "JSON (*.json)",
        )
        try:
            import_piper_voice(
                Path(root_text), name.strip(), Path(model), Path(config) if config else None
            )
        except Exception as exc:
            QMessageBox.critical(self, "Piper voice import error", str(exc))
        else:
            QMessageBox.information(self, "Piper voice imported", f"Imported {name.strip()!r}.")

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
            output_device=str(
                self.output_device_input.currentData()
                or self.output_device_input.currentText().strip()
            ),
            output_latency=self.latency_input.currentText(),
            output_blocksize=self.blocksize_input.value(),
        )
