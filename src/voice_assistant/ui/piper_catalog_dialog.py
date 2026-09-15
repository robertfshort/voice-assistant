from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
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
        self.setWindowTitle("Download Piper voices")
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by voice, language, country, or quality")
        self.search_input.textChanged.connect(self._refresh)
        layout.addWidget(self.search_input)
        layout.addWidget(QLabel("Select one or more voices. Use Ctrl or Shift to select several."))
        self.voice_list = QListWidget()
        self.voice_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.voice_list.currentRowChanged.connect(self._show_selected)
        self.voice_list.itemSelectionChanged.connect(self._selection_changed)
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
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        self.download_button = QPushButton("Download and register")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._confirm_download)
        controls.addWidget(self.close_button)
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

    def _selected_voices(self) -> tuple[PiperCatalogVoice, ...]:
        voices: list[PiperCatalogVoice] = []
        for item in self.voice_list.selectedItems():
            value = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(value, PiperCatalogVoice):
                voices.append(value)
        return tuple(voices)

    def _selection_changed(self) -> None:
        count = len(self._selected_voices())
        self.download_button.setEnabled(count > 0)
        self.download_button.setText(
            f"Download and register {count} voices" if count > 1 else "Download and register"
        )

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
        voices = self._selected_voices()
        if not voices:
            return
        installed = load_voice_registry(self._voice_root).piper
        replacements = {
            voice.key for voice in voices if portable_voice_name(voice.key) in installed
        }
        total_bytes = sum(voice.size_bytes for voice in voices)
        names = "\n".join(f"• {voice.key}" for voice in voices)
        replacement_note = (
            f"\n\n{len(replacements)} installed voice(s) will be replaced." if replacements else ""
        )
        answer = QMessageBox.question(
            self,
            "Download Piper voices?",
            f"Download and register {len(voices)} voice(s) "
            f"({total_bytes / (1024 * 1024):.1f} MiB total)?\n\n{names}{replacement_note}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.download_button.setEnabled(False)
        self.download_button.setText(f"Downloading 1 of {len(voices)}…")
        self.search_input.setEnabled(False)
        self.voice_list.setEnabled(False)
        self.close_button.setEnabled(False)
        self.progress.setRange(0, max(1, total_bytes))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        asyncio.create_task(self._download(voices, replacements=replacements))

    def _update_progress(self, downloaded: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(downloaded)

    async def _download(
        self, voices: tuple[PiperCatalogVoice, ...], *, replacements: set[str]
    ) -> None:
        registered: list[str] = []
        failures: list[str] = []
        total_bytes = sum(voice.size_bytes for voice in voices)
        completed_bytes = 0
        for index, voice in enumerate(voices, start=1):
            self.download_button.setText(f"Downloading {index} of {len(voices)}…")

            def report(downloaded: int, _total: int, *, offset: int = completed_bytes) -> None:
                self.download_progress.emit(offset + downloaded, total_bytes)

            try:
                name = await download_piper_voice(
                    voice,
                    self._voice_root,
                    report,
                    replace=voice.key in replacements,
                )
            except Exception as exc:
                failures.append(f"{voice.key}: {exc}")
            else:
                registered.append(name)
            completed_bytes += voice.size_bytes
            self.download_progress.emit(completed_bytes, total_bytes)

        if registered:
            message = "Registered:\n" + "\n".join(f"• {name}" for name in registered)
            if failures:
                message += "\n\nFailed:\n" + "\n".join(f"• {failure}" for failure in failures)
                QMessageBox.warning(self, "Piper downloads completed with errors", message)
            else:
                QMessageBox.information(self, "Piper voices downloaded", message)
        else:
            QMessageBox.critical(
                self,
                "Piper download error",
                "No voices were installed:\n" + "\n".join(f"• {failure}" for failure in failures),
            )
        self.search_input.setEnabled(True)
        self.voice_list.setEnabled(True)
        self.close_button.setEnabled(True)
        self.progress.setVisible(False)
        self._selection_changed()
