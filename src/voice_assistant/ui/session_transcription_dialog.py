from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class SessionTranscriptionReviewDialog(QDialog):
    def __init__(self, text: str, speakers: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review transcription")
        self.resize(600, 420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Transcribed text"))
        self._text_edit = QTextEdit(text)
        layout.addWidget(self._text_edit, 1)
        layout.addWidget(QLabel("Speaker"))
        self._speaker_input = QComboBox()
        self._speaker_input.setEditable(True)
        self._speaker_input.addItems(speakers)
        layout.addWidget(self._speaker_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def speaker(self) -> str:
        return self._speaker_input.currentText().strip()

    def transcript(self) -> str:
        return self._text_edit.toPlainText().strip()
