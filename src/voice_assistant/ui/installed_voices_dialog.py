from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.storage.voices import load_voice_registry, remove_piper_voice


class InstalledVoicesDialog(QDialog):
    def __init__(self, voice_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._voice_root = voice_root
        self.setWindowTitle("Installed Piper voices")
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        self.voice_list = QListWidget()
        self.voice_list.currentRowChanged.connect(self._show_selected)
        layout.addWidget(self.voice_list, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        controls = QHBoxLayout()
        controls.addStretch()
        self.remove_button = QPushButton("Remove voice…")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._remove_selected)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        controls.addWidget(self.remove_button)
        controls.addWidget(close_button)
        layout.addLayout(controls)
        self._refresh()

    def _refresh(self) -> None:
        self.voice_list.clear()
        registry = load_voice_registry(self._voice_root)
        for name, asset in sorted(registry.piper.items()):
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, (name, asset.model, asset.config))
            self.voice_list.addItem(item)
        if self.voice_list.count():
            self.voice_list.setCurrentRow(0)
        else:
            self.details.setText("No Piper voices are registered in this folder.")
            self.remove_button.setEnabled(False)

    def _selected(self) -> tuple[str, str, str] | None:
        item = self.voice_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if isinstance(value, tuple) and len(value) == 3:
            return str(value[0]), str(value[1]), str(value[2])
        return None

    def _show_selected(self) -> None:
        selected = self._selected()
        if selected is None:
            self.remove_button.setEnabled(False)
            return
        name, model, config = selected
        self.details.setText(f"Name: {name}\nModel: {model}\nConfig: {config or 'Model default'}")
        self.remove_button.setEnabled(True)

    def _remove_selected(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        name = selected[0]
        answer = QMessageBox.warning(
            self,
            "Remove Piper voice?",
            f"Remove {name!r} from the registry and delete its model files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            remove_piper_voice(self._voice_root, name)
        except Exception as exc:
            QMessageBox.critical(self, "Piper voice removal error", str(exc))
        else:
            self._refresh()
