from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.services.piper_catalog import (
    PiperCatalogVoice,
    download_piper_voice,
    fetch_model_card,
    fetch_piper_catalog,
    portable_voice_name,
)
from voice_assistant.storage.voices import load_voice_registry


class PiperCatalogDialog(QDialog):
    download_progress = Signal(int, int)

    def __init__(self, voice_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._voice_root = voice_root
        self._voices: tuple[PiperCatalogVoice, ...] = ()
        self.setWindowTitle("Download Piper voice")
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by voice, language, country, or quality")
        self.search_input.textChanged.connect(self._refresh)
        layout.addWidget(self.search_input)
        self.voice_list = QListWidget()
        self.voice_list.currentRowChanged.connect(self._show_selected)
        layout.addWidget(self.voice_list, 1)
        self.details = QLabel("Loading Piper voice catalog…")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.download_progress.connect(self._update_progress)
        controls = QHBoxLayout()
        controls.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        self.download_button = QPushButton("Download and register")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._confirm_download)
        controls.addWidget(close_button)
        controls.addWidget(self.download_button)
        layout.addLayout(controls)
        asyncio.create_task(self._load_catalog())

    async def _load_catalog(self) -> None:
        try:
            self._voices = await fetch_piper_catalog(self._voice_root / ".cache")
        except Exception as exc:
            self.details.setText(f"Unable to load Piper catalog: {exc}")
        else:
            self._refresh()

    def _refresh(self) -> None:
        query = self.search_input.text().strip().lower()
        self.voice_list.clear()
        for voice in self._voices:
            searchable = f"{voice.key} {voice.language} {voice.country} {voice.quality}".lower()
            if query and query not in searchable:
                continue
            item = QListWidgetItem(
                f"{voice.key} — {voice.language} ({voice.quality}, {voice.size_mib:.1f} MiB)"
            )
            item.setData(Qt.ItemDataRole.UserRole, voice)
            self.voice_list.addItem(item)
        if self.voice_list.count():
            self.voice_list.setCurrentRow(0)
        else:
            self.details.setText("No matching Piper voices.")
            self.download_button.setEnabled(False)

    def _selected(self) -> PiperCatalogVoice | None:
        item = self.voice_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return value if isinstance(value, PiperCatalogVoice) else None

    def _show_selected(self) -> None:
        voice = self._selected()
        if voice is None:
            self.download_button.setEnabled(False)
            return
        self.details.setText(
            f"{voice.language} — {voice.country or 'Unspecified country'}\n"
            f"Quality: {voice.quality}; speakers: {voice.speakers}; "
            f"download: {voice.size_mib:.1f} MiB\n"
            "License: loading upstream model card…"
        )
        self.download_button.setEnabled(True)
        asyncio.create_task(self._load_model_card(voice))

    async def _load_model_card(self, voice: PiperCatalogVoice) -> None:
        try:
            card = await fetch_model_card(voice, self._voice_root / ".cache")
        except Exception as exc:
            license_text = f"Unable to load model card: {exc}"
        else:
            license_text = card.license
        if self._selected() == voice:
            details = self.details.text().replace("loading upstream model card…", license_text)
            self.details.setText(details)

    def _confirm_download(self) -> None:
        voice = self._selected()
        if voice is None:
            return
        registered_name = portable_voice_name(voice.key)
        replace = registered_name in load_voice_registry(self._voice_root).piper
        action = "replace the installed copy" if replace else "register it locally"
        answer = QMessageBox.question(
            self,
            "Update Piper voice?" if replace else "Download Piper voice?",
            f"Download {voice.key} ({voice.size_mib:.1f} MiB) and {action}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.download_button.setEnabled(False)
        self.download_button.setText("Downloading…")
        self.progress.setRange(0, max(1, voice.size_bytes))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        asyncio.create_task(self._download(voice, replace=replace))

    def _update_progress(self, downloaded: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(downloaded)

    async def _download(self, voice: PiperCatalogVoice, *, replace: bool = False) -> None:
        try:
            registered_name = await download_piper_voice(
                voice, self._voice_root, self.download_progress.emit, replace=replace
            )
        except Exception as exc:
            QMessageBox.critical(self, "Piper download error", str(exc))
            self.download_button.setEnabled(True)
        else:
            QMessageBox.information(
                self,
                "Piper voice downloaded",
                f"Registered as {registered_name!r}. Use this name in the NPC editor.",
            )
        finally:
            self.download_button.setText("Download and register")
            self.progress.setVisible(False)
