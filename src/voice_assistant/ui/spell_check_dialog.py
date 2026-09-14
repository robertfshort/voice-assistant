from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.services.spell_check import CampaignSpellCheck
from voice_assistant.storage.dictionary import append_to_campaign_dictionary


class SpellCheckDialog(QDialog):
    def __init__(
        self,
        campaign_directory: Path,
        unknown_words: list[str],
        spell_check: CampaignSpellCheck,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Spell check")
        self._campaign_directory = campaign_directory
        self._spell_check = spell_check
        self._unknown = list(unknown_words)

        layout = QVBoxLayout(self)

        info = QLabel("Select a word to see suggestions, then add it to the campaign dictionary.")
        info.setWordWrap(True)
        layout.addWidget(info)

        columns = QHBoxLayout()
        self._word_list = QListWidget()
        self._word_list.addItems(self._unknown)
        columns.addWidget(self._word_list)

        right = QVBoxLayout()
        self._suggestion_label = QLabel("Suggestions: —")
        self._suggestion_label.setWordWrap(True)
        right.addWidget(self._suggestion_label)
        columns.addLayout(right)
        layout.addLayout(columns)

        buttons = QHBoxLayout()
        self._add_button = QPushButton("Add to dictionary")
        add_all_button = QPushButton("Add all")
        close_button = QPushButton("Close")
        for button in (self._add_button, add_all_button, close_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self._add_button.clicked.connect(self._add_selected)
        add_all_button.clicked.connect(self._add_all)
        close_button.clicked.connect(self.accept)
        self._word_list.currentTextChanged.connect(self._show_suggestions)

        if self._word_list.count():
            self._word_list.setCurrentRow(0)

    def _show_suggestions(self, word: str) -> None:
        if not word:
            self._suggestion_label.setText("Suggestions: —")
            return
        suggestions = self._spell_check.candidates(word)
        text = "Suggestions: " + (", ".join(suggestions) if suggestions else "—")
        self._suggestion_label.setText(text)

    def _add_selected(self) -> None:
        item = self._word_list.currentItem()
        if item is None:
            return
        word = item.text()
        self._add_words([word])

    def _add_all(self) -> None:
        self._add_words(self._unknown)

    def _add_words(self, words: list[str]) -> None:
        append_to_campaign_dictionary(self._campaign_directory, words)
        for word in words:
            self._spell_check._spell.word_frequency.add(word.lower())
            for index in range(self._word_list.count() - 1, -1, -1):
                if self._word_list.item(index).text() == word:
                    self._word_list.takeItem(index)
                    break
        self._unknown = [
            self._word_list.item(index).text() for index in range(self._word_list.count())
        ]
        self._add_button.setEnabled(self._word_list.count() > 0)
