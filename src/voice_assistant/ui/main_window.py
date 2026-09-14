from __future__ import annotations

import asyncio
import html
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.domain.models import Campaign, Npc, SpeakerProfile
from voice_assistant.services.conversation import explain_npc_lore
from voice_assistant.services.session_notes import SessionNotes, propose_session_notes
from voice_assistant.services.spell_check import CampaignSpellCheck
from voice_assistant.services.voice_preview import preview_voice, tts_segments
from voice_assistant.services.voice_session import VoiceSessionController
from voice_assistant.storage.campaigns import create_campaign, discover_campaigns, load_campaign
from voice_assistant.storage.credentials import CredentialStore
from voice_assistant.storage.lore import create_lore, save_lore
from voice_assistant.storage.npc_creation import create_npc, draft_from_npc, update_npc
from voice_assistant.storage.npc_knowledge import append_npc_knowledge, save_npc_knowledge
from voice_assistant.storage.npc_lore_proposals import (
    propose_npc_lore,
    render_lore_file,
    save_lore_proposal,
)
from voice_assistant.storage.speakers import create_speaker, save_speaker
from voice_assistant.storage.transcripts import append_transcript, load_transcript
from voice_assistant.ui.npc_dialog import NpcDialog
from voice_assistant.ui.spell_check_dialog import SpellCheckDialog
from voice_assistant.ui.themes import THEME_NAMES, apply_theme


class MainWindow(QMainWindow):
    campaign_root_changed = Signal(Path)
    theme_changed = Signal(str)

    def __init__(self, campaign_root: Path, *, theme: str = "light") -> None:
        super().__init__()
        self._campaign_root = campaign_root
        self._campaigns: tuple[Campaign, ...] = ()
        self._active_campaign: Campaign | None = None
        self._active_npc: Npc | None = None
        self._active_speaker: SpeakerProfile | None = None
        self._active_lore_id: str | None = None
        self._recording_session_id: str | None = None
        self._credentials = CredentialStore()
        self._voice_session = VoiceSessionController()
        self._voice_session.state_changed.connect(self._voice_state_changed)
        self._voice_session.transcription.connect(self._receive_transcription)
        self._voice_session.error.connect(self._voice_error)
        self.setWindowTitle("RPG Voice Assistant")
        self.resize(1100, 720)
        self._build_ui()
        self._build_theme_menu(theme)
        self.load_campaign_root(campaign_root)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        path_row = QHBoxLayout()
        self._campaign_path = QLineEdit()
        self._campaign_path.setReadOnly(True)
        choose_button = QPushButton("Choose campaign folder")
        choose_button.clicked.connect(self._choose_campaign_root)
        up_button = QPushButton("Up one level")
        up_button.clicked.connect(self._move_campaign_root_up)
        new_campaign_button = QPushButton("New campaign")
        new_campaign_button.clicked.connect(self._new_campaign)
        path_row.addWidget(QLabel("Campaigns folder"))
        path_row.addWidget(self._campaign_path, 1)
        path_row.addWidget(up_button)
        path_row.addWidget(new_campaign_button)
        path_row.addWidget(choose_button)
        layout.addLayout(path_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        selection = QWidget()
        selection_layout = QVBoxLayout(selection)
        selection_layout.addWidget(QLabel("Campaigns"))
        self._campaign_list = QListWidget()
        self._campaign_list.currentRowChanged.connect(self._select_campaign)
        selection_layout.addWidget(self._campaign_list)
        selection_layout.addWidget(QLabel("NPCs"))
        self._npc_list = QListWidget()
        self._npc_list.currentRowChanged.connect(self._select_npc)
        selection_layout.addWidget(self._npc_list)
        self._add_npc_button = QPushButton("Create NPC")
        self._add_npc_button.setEnabled(False)
        self._add_npc_button.clicked.connect(self._create_npc)
        selection_layout.addWidget(self._add_npc_button)
        self._edit_npc_button = QPushButton("Edit NPC")
        self._edit_npc_button.setEnabled(False)
        self._edit_npc_button.clicked.connect(self._edit_npc)
        selection_layout.addWidget(self._edit_npc_button)
        self._duplicate_npc_button = QPushButton("Duplicate NPC")
        self._duplicate_npc_button.setEnabled(False)
        self._duplicate_npc_button.clicked.connect(self._duplicate_npc)
        selection_layout.addWidget(self._duplicate_npc_button)
        self._propose_lore_button = QPushButton("Propose public lore")
        self._propose_lore_button.setEnabled(False)
        self._propose_lore_button.clicked.connect(self._propose_npc_lore)
        selection_layout.addWidget(self._propose_lore_button)
        splitter.addWidget(selection)

        tabs = QTabWidget()
        conversation = QWidget()
        conversation_layout = QVBoxLayout(conversation)
        self._npc_heading = QLabel("No NPC selected")
        self._npc_heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        conversation_layout.addWidget(self._npc_heading)
        self._profile = QTextEdit()
        self._profile.setReadOnly(True)
        conversation_layout.addWidget(self._profile, 2)

        conversation_layout.addWidget(QLabel("Conversation"))
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._transcript.customContextMenuRequested.connect(self._show_transcript_menu)
        conversation_layout.addWidget(self._transcript, 2)

        input_form = QFormLayout()
        self._player_input = QLineEdit()
        self._player_input.setPlaceholderText("In-character player dialogue")
        self._player_input.returnPressed.connect(self._send_player_text)
        self._gm_input = QLineEdit()
        self._gm_input.setPlaceholderText("Private out-of-character GM instruction")
        self._gm_input.returnPressed.connect(self._send_gm_text)
        input_form.addRow("Player says", self._player_input)
        input_form.addRow("GM directs", self._gm_input)
        self._gm_request_response = QCheckBox("Request an NPC response")
        self._gm_request_response.setToolTip(
            "Unchecked: silently update NPC direction. Checked: ask the NPC to answer the GM."
        )
        input_form.addRow("GM mode", self._gm_request_response)
        conversation_layout.addLayout(input_form)

        controls = QHBoxLayout()
        self._start_button = QPushButton("Start voice session")
        self._start_button.setEnabled(False)
        self._start_button.clicked.connect(self._toggle_voice_session)
        provider_button = QPushButton("Gemini API key")
        provider_button.clicked.connect(self._configure_gemini_key)
        player_button = QPushButton("Send player text")
        player_button.clicked.connect(self._send_player_text)
        gm_button = QPushButton("Send private GM instruction")
        gm_button.clicked.connect(self._send_gm_text)
        self._inspect_button = QPushButton("Inspect context")
        self._inspect_button.setEnabled(False)
        self._inspect_button.clicked.connect(self._inspect_npc_context)
        self._session_notes_button = QPushButton("Generate session notes")
        self._session_notes_button.setEnabled(False)
        self._session_notes_button.clicked.connect(self._on_generate_session_notes)
        self._speak_as_npc_button = QPushButton("Speak as NPC")
        self._speak_as_npc_button.setEnabled(False)
        self._speak_as_npc_button.clicked.connect(self._on_speak_as_npc)
        self._record_button = QPushButton("Record session")
        self._record_button.setEnabled(False)
        self._record_button.clicked.connect(self._toggle_session_recording)
        controls.addWidget(self._start_button)
        controls.addWidget(provider_button)
        controls.addStretch()
        controls.addWidget(player_button)
        controls.addWidget(gm_button)
        controls.addWidget(self._inspect_button)
        controls.addWidget(self._session_notes_button)
        controls.addWidget(self._speak_as_npc_button)
        controls.addWidget(self._record_button)
        conversation_layout.addLayout(controls)
        tabs.addTab(conversation, "NPC conversation")

        knowledge = QWidget()
        knowledge_layout = QVBoxLayout(knowledge)
        self._knowledge_heading = QLabel("No NPC selected")
        self._knowledge_heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        knowledge_layout.addWidget(self._knowledge_heading)
        knowledge_layout.addWidget(QLabel("NPC knowledge and persistent memory"))
        self._knowledge_editor = QTextEdit()
        self._knowledge_editor.setEnabled(False)
        knowledge_layout.addWidget(self._knowledge_editor, 3)
        knowledge_layout.addWidget(QLabel("Append knowledge without replacing existing text"))
        self._knowledge_append = QTextEdit()
        self._knowledge_append.setMaximumHeight(120)
        self._knowledge_append.setEnabled(False)
        knowledge_layout.addWidget(self._knowledge_append)
        knowledge_controls = QHBoxLayout()
        self._save_knowledge_button = QPushButton("Save edited knowledge")
        self._save_knowledge_button.setEnabled(False)
        self._save_knowledge_button.clicked.connect(self._save_npc_knowledge)
        self._append_knowledge_button = QPushButton("Append knowledge")
        self._append_knowledge_button.setEnabled(False)
        self._append_knowledge_button.clicked.connect(self._append_npc_knowledge)
        self._spell_check_knowledge_button = QPushButton("Spell check")
        self._spell_check_knowledge_button.setEnabled(False)
        self._spell_check_knowledge_button.clicked.connect(self._spell_check_knowledge)
        knowledge_controls.addStretch()
        knowledge_controls.addWidget(self._save_knowledge_button)
        knowledge_controls.addWidget(self._append_knowledge_button)
        knowledge_controls.addWidget(self._spell_check_knowledge_button)
        knowledge_layout.addLayout(knowledge_controls)
        tabs.addTab(knowledge, "NPC knowledge")

        lore = QWidget()
        lore_layout = QVBoxLayout(lore)
        lore_layout.addWidget(QLabel("Campaign lore"))
        self._lore_filter = QLineEdit()
        self._lore_filter.setPlaceholderText("Filter lore by title or content")
        self._lore_filter.textChanged.connect(self._load_lore_list)
        lore_layout.addWidget(self._lore_filter)
        self._lore_list = QListWidget()
        self._lore_list.currentRowChanged.connect(self._select_lore)
        lore_layout.addWidget(self._lore_list, 1)
        self._lore_editor = QTextEdit()
        self._lore_editor.setPlaceholderText("Select a lore file to view or edit it")
        self._lore_editor.setEnabled(False)
        lore_layout.addWidget(self._lore_editor, 3)
        lore_metadata = QHBoxLayout()
        lore_metadata.addWidget(QLabel("Insert"))
        for label, snippet in [
            ("Public", "---\nvisibility: public\n---\n\n"),
            ("Restricted", "---\nvisibility: restricted\nscopes:\n  - \n---\n\n"),
            ("Secret", "---\nvisibility: secret\n---\n\n"),
            ("GM-only", "---\nvisibility: gm-only\n---\n\n"),
            ("Proposed", "---\nstatus: proposed\n---\n\n"),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, text=snippet: self._insert_lore_snippet(text))
            lore_metadata.addWidget(button)
        self._lore_scope_input = QLineEdit()
        self._lore_scope_input.setPlaceholderText("order-of-the-rose")
        lore_scope_button = QPushButton("Group scope")
        lore_scope_button.clicked.connect(lambda _: self._insert_lore_scope())
        lore_metadata.addWidget(self._lore_scope_input)
        lore_metadata.addWidget(lore_scope_button)
        lore_metadata.addStretch()
        lore_layout.addLayout(lore_metadata)
        lore_controls = QHBoxLayout()
        self._new_lore_button = QPushButton("Create lore entry")
        self._new_lore_button.setEnabled(False)
        self._new_lore_button.clicked.connect(self._create_lore)
        self._save_lore_button = QPushButton("Save lore")
        self._save_lore_button.setEnabled(False)
        self._save_lore_button.clicked.connect(self._save_lore)
        self._spell_check_button = QPushButton("Spell check")
        self._spell_check_button.setEnabled(False)
        self._spell_check_button.clicked.connect(self._spell_check_lore)
        lore_controls.addStretch()
        lore_controls.addWidget(self._new_lore_button)
        lore_controls.addWidget(self._save_lore_button)
        lore_controls.addWidget(self._spell_check_button)
        lore_layout.addLayout(lore_controls)
        tabs.addTab(lore, "Lore")

        speakers = QWidget()
        speakers_layout = QVBoxLayout(speakers)
        speakers_layout.addWidget(QLabel("Speaker profiles"))
        self._speaker_list = QListWidget()
        self._speaker_list.currentRowChanged.connect(self._select_speaker)
        speakers_layout.addWidget(self._speaker_list, 1)
        self._speaker_name = QLineEdit()
        self._speaker_name.setEnabled(False)
        self._speaker_name.setPlaceholderText("Speaker name")
        speakers_layout.addWidget(self._speaker_name)
        self._speaker_active = QCheckBox("Active in this session")
        self._speaker_active.setEnabled(False)
        speakers_layout.addWidget(self._speaker_active)
        speakers_layout.addWidget(QLabel("Public background"))
        self._speaker_editor = QTextEdit()
        self._speaker_editor.setPlaceholderText(
            "Select a speaker to view or edit their public background"
        )
        self._speaker_editor.setEnabled(False)
        speakers_layout.addWidget(self._speaker_editor, 3)
        speaker_controls = QHBoxLayout()
        self._new_speaker_button = QPushButton("Create speaker")
        self._new_speaker_button.setEnabled(False)
        self._new_speaker_button.clicked.connect(self._create_speaker)
        self._save_speaker_button = QPushButton("Save speaker")
        self._save_speaker_button.setEnabled(False)
        self._save_speaker_button.clicked.connect(self._save_speaker)
        self._spell_check_speaker_button = QPushButton("Spell check")
        self._spell_check_speaker_button.setEnabled(False)
        self._spell_check_speaker_button.clicked.connect(self._spell_check_speaker)
        speaker_controls.addStretch()
        speaker_controls.addWidget(self._new_speaker_button)
        speaker_controls.addWidget(self._save_speaker_button)
        speaker_controls.addWidget(self._spell_check_speaker_button)
        speakers_layout.addLayout(speaker_controls)
        tabs.addTab(speakers, "Speakers")

        session = QWidget()
        session_layout = QVBoxLayout(session)
        session_layout.addWidget(QLabel("Table sessions"))
        self._session_list = QListWidget()
        self._session_list.currentRowChanged.connect(self._select_session)
        session_layout.addWidget(self._session_list, 1)
        self._session_display = QTextEdit()
        self._session_display.setReadOnly(True)
        self._session_display.setPlaceholderText("Select a table session to view the transcript")
        session_layout.addWidget(self._session_display, 3)
        session_controls = QHBoxLayout()
        self._stop_session_button = QPushButton("Stop recording")
        self._stop_session_button.setEnabled(False)
        self._stop_session_button.clicked.connect(self._toggle_session_recording)
        session_controls.addWidget(self._stop_session_button)
        session_controls.addStretch()
        session_layout.addLayout(session_controls)
        tabs.addTab(session, "Session")

        splitter.addWidget(tabs)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def load_campaign_root(self, campaign_root: Path) -> None:
        self._campaign_root = campaign_root.resolve()
        self._campaign_path.setText(str(self._campaign_root))
        try:
            self._campaigns = discover_campaigns(self._campaign_root)
        except ValueError as exc:
            QMessageBox.critical(self, "Campaign error", str(exc))
            self._campaigns = ()
        self._campaign_list.clear()
        self._npc_list.clear()
        self._lore_list.clear()
        self._lore_editor.clear()
        self._lore_editor.setEnabled(False)
        self._save_lore_button.setEnabled(False)
        self._spell_check_button.setEnabled(False)
        self._new_lore_button.setEnabled(False)
        self._spell_check_button.setEnabled(False)
        self._active_lore_id = None
        self._profile.clear()
        self._knowledge_editor.clear()
        self._knowledge_editor.setEnabled(False)
        self._knowledge_append.clear()
        self._knowledge_append.setEnabled(False)
        self._save_knowledge_button.setEnabled(False)
        self._append_knowledge_button.setEnabled(False)
        self._spell_check_knowledge_button.setEnabled(False)
        self._npc_heading.setText("No NPC selected")
        self._knowledge_heading.setText("No NPC selected")
        self._edit_npc_button.setEnabled(False)
        self._duplicate_npc_button.setEnabled(False)
        for campaign in self._campaigns:
            self._campaign_list.addItem(campaign.manifest.name)
        if self._campaigns:
            self._campaign_list.setCurrentRow(0)
        self.statusBar().showMessage(f"Loaded {len(self._campaigns)} campaign(s)")

    def _build_theme_menu(self, theme: str) -> None:
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu("Settings")
        theme_menu = settings_menu.addMenu("Theme")
        group = QActionGroup(self)
        group.setExclusive(True)
        for name in THEME_NAMES:
            action = QAction(name.capitalize(), self)
            action.setCheckable(True)
            action.setData(name)
            action.setChecked(name == theme)
            theme_menu.addAction(action)
            group.addAction(action)
        group.triggered.connect(self._on_theme_changed)

    def _on_theme_changed(self, action: QAction) -> None:
        name = str(action.data())
        apply_theme(name)
        self.theme_changed.emit(name)

    def _choose_campaign_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose campaigns folder",
            str(self._campaign_root),
        )
        if selected:
            path = Path(selected)
            self.load_campaign_root(path)
            self.campaign_root_changed.emit(path)

    def _move_campaign_root_up(self) -> None:
        parent = self._campaign_root.parent
        if parent == self._campaign_root:
            return
        self.load_campaign_root(parent)
        self.campaign_root_changed.emit(parent)

    def _new_campaign(self) -> None:
        campaign_id, accepted = QInputDialog.getText(
            self,
            "New campaign",
            "Campaign folder ID (lowercase with hyphens):",
            text="my-campaign",
        )
        if not accepted or not campaign_id.strip():
            return
        campaign_id = campaign_id.strip().lower()
        name, accepted = QInputDialog.getText(
            self,
            "New campaign",
            "Campaign name:",
            text=campaign_id.replace("-", " ").title(),
        )
        if not accepted or not name.strip():
            return
        try:
            create_campaign(self._campaign_root, campaign_id, name.strip())
        except ValueError as exc:
            QMessageBox.critical(self, "Campaign creation error", str(exc))
            return
        self.load_campaign_root(self._campaign_root)
        row = next(
            index
            for index, campaign in enumerate(self._campaigns)
            if campaign.manifest.id == campaign_id
        )
        self._campaign_list.setCurrentRow(row)

    def _select_campaign(self, row: int) -> None:
        self._active_campaign = self._campaigns[row] if 0 <= row < len(self._campaigns) else None
        self._active_npc = None
        self._active_speaker = None
        self._active_lore_id = None
        self._npc_list.clear()
        self._lore_list.clear()
        self._speaker_list.clear()
        self._lore_editor.clear()
        self._lore_editor.setEnabled(False)
        self._save_lore_button.setEnabled(False)
        self._spell_check_button.setEnabled(False)
        self._speaker_name.clear()
        self._speaker_name.setEnabled(False)
        self._speaker_active.setChecked(False)
        self._speaker_active.setEnabled(False)
        self._speaker_editor.clear()
        self._speaker_editor.setEnabled(False)
        self._save_speaker_button.setEnabled(False)
        self._spell_check_speaker_button.setEnabled(False)
        self._add_npc_button.setEnabled(self._active_campaign is not None)
        self._new_lore_button.setEnabled(self._active_campaign is not None)
        self._new_speaker_button.setEnabled(self._active_campaign is not None)
        self._record_button.setEnabled(self._active_campaign is not None)
        self._stop_session_button.setEnabled(False)
        if self._recording_session_id is not None:
            self._recording_session_id = None
            self._record_button.setText("Record session")
        self._session_list.clear()
        self._session_display.clear()
        if self._active_campaign is not None:
            self._load_session_list()
        if self._active_campaign is None:
            return
        for npc in self._active_campaign.npcs:
            label = f"{npc.name} (archived)" if npc.archived else npc.name
            item = QListWidgetItem(label)
            if npc.archived:
                item.setForeground(QColor("gray"))
            self._npc_list.addItem(item)
        self._load_lore_list()
        for speaker in self._active_campaign.speakers:
            label = f"{speaker.name} (active)" if speaker.active else speaker.name
            self._speaker_list.addItem(label)
        if self._speaker_list.count():
            self._speaker_list.setCurrentRow(0)
        default_id = self._active_campaign.manifest.default_npc
        default_index = next(
            (
                index
                for index, npc in enumerate(self._active_campaign.npcs)
                if npc.id == default_id
            ),
            0,
        )
        self._npc_list.setCurrentRow(default_index)

    def _load_session_list(self) -> None:
        if self._active_campaign is None:
            return
        sessions = self._active_campaign.directory / "sessions"
        if not sessions.exists():
            return
        files = sorted(
            path
            for path in sessions.iterdir()
            if path.suffix == ".jsonl" and path.stem.startswith("table-")
        )
        for path in files:
            self._session_list.addItem(path.stem)

    def _select_session(self, row: int) -> None:
        self._session_display.clear()
        if self._active_campaign is None or not (0 <= row < self._session_list.count()):
            return
        session_id = self._session_list.item(row).text()
        try:
            entries = load_transcript(self._active_campaign.directory, session_id)
        except ValueError as exc:
            QMessageBox.critical(self, "Session load error", str(exc))
            return
        lines: list[str] = []
        for entry in entries:
            label = "GM (private)" if entry.private else entry.speaker.capitalize()
            lines.append(f"<b>{html.escape(label)}:</b> {html.escape(entry.text)}")
        self._session_display.setHtml("<br>".join(lines))

    def _select_speaker(self, row: int) -> None:
        if self._active_campaign is None or not (0 <= row < len(self._active_campaign.speakers)):
            self._active_speaker = None
            self._speaker_name.clear()
            self._speaker_name.setEnabled(False)
            self._speaker_active.setChecked(False)
            self._speaker_active.setEnabled(False)
            self._speaker_editor.clear()
            self._speaker_editor.setEnabled(False)
            self._save_speaker_button.setEnabled(False)
            return
        self._active_speaker = self._active_campaign.speakers[row]
        self._speaker_name.setText(self._active_speaker.name)
        self._speaker_name.setEnabled(True)
        self._speaker_active.setChecked(self._active_speaker.active)
        self._speaker_active.setEnabled(True)
        self._speaker_editor.setPlainText(self._active_speaker.profile)
        self._speaker_editor.setEnabled(True)
        self._save_speaker_button.setEnabled(True)
        self._spell_check_speaker_button.setEnabled(True)

    def _create_speaker(self) -> None:
        if self._active_campaign is None:
            return
        speaker_id, accepted = QInputDialog.getText(
            self,
            "Create speaker",
            "Speaker ID (used for the filename)",
            text="new-speaker",
        )
        if not accepted or not speaker_id.strip():
            return
        speaker_id = speaker_id.strip().replace(" ", "-").lower()
        name, accepted = QInputDialog.getText(
            self,
            "Create speaker",
            "Display name",
            text=speaker_id.replace("-", " ").title(),
        )
        if not accepted or not name.strip():
            return
        try:
            create_speaker(self._active_campaign.directory, speaker_id, name.strip())
        except ValueError as exc:
            QMessageBox.critical(self, "Speaker creation error", str(exc))
            return
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        new_row = next(
            index
            for index, speaker in enumerate(updated_campaign.speakers)
            if speaker.id == speaker_id
        )
        self._speaker_list.setCurrentRow(new_row)
        self.statusBar().showMessage(f"Created speaker: {speaker_id}")

    def _save_speaker(self) -> None:
        if self._active_campaign is None or self._active_speaker is None:
            return
        reason, accepted = QInputDialog.getText(
            self,
            "Reason for change",
            "Optional change note",
        )
        if not accepted:
            return
        updated = self._active_speaker.model_copy(
            update={
                "name": self._speaker_name.text().strip() or self._active_speaker.name,
                "profile": self._speaker_editor.toPlainText().strip(),
                "active": self._speaker_active.isChecked(),
            }
        )
        try:
            save_speaker(
                self._active_campaign.directory,
                updated,
                reason=reason.strip() if reason.strip() else "",
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Speaker save error", str(exc))
            return
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        new_row = next(
            index
            for index, speaker in enumerate(updated_campaign.speakers)
            if speaker.id == updated.id
        )
        self._speaker_list.setCurrentRow(new_row)
        self.statusBar().showMessage(f"Saved speaker: {updated.id}")

    def _create_npc(self) -> None:
        if self._active_campaign is None:
            return
        dialog = NpcDialog(self, credentials=self._credentials)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            draft = dialog.draft()
            create_npc(self._active_campaign.directory, draft)
            updated_campaign = load_campaign(self._active_campaign.directory)
        except ValueError as exc:
            QMessageBox.critical(self, "NPC creation error", str(exc))
            return
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        new_row = next(
            index for index, npc in enumerate(updated_campaign.npcs) if npc.id == draft.id
        )
        self._npc_list.setCurrentRow(new_row)
        self._maybe_offer_public_lore()
        self.statusBar().showMessage(f"Created NPC: {draft.name}")

    def _edit_npc(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        npc_id = self._active_npc.id
        dialog = NpcDialog(
            self, credentials=self._credentials, draft=draft_from_npc(self._active_npc)
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            draft = dialog.draft()
            update_npc(self._active_campaign.directory, draft)
            updated_campaign = load_campaign(self._active_campaign.directory)
        except ValueError as exc:
            QMessageBox.critical(self, "NPC editing error", str(exc))
            return
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        row = next(index for index, npc in enumerate(updated_campaign.npcs) if npc.id == npc_id)
        self._npc_list.setCurrentRow(row)
        self._maybe_offer_public_lore()
        self.statusBar().showMessage(f"Updated NPC: {draft.name}")

    def _maybe_offer_public_lore(self) -> None:
        if self._active_npc is None:
            return
        if propose_npc_lore(self._active_npc) is None:
            return
        reply = QMessageBox.question(
            self,
            "Add public lore?",
            "Public facts about this NPC can be added to campaign lore. Review the proposal?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._propose_npc_lore()

    def _duplicate_npc(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        source = self._active_npc
        default_id = f"{source.id}-copy"
        new_id, accepted = QInputDialog.getText(
            self,
            "Duplicate NPC",
            "New stable ID for the copy",
            text=default_id,
        )
        new_id = new_id.strip()
        if not accepted or not new_id:
            return
        if new_id == source.id:
            QMessageBox.critical(
                self, "Duplicate NPC error", "The new ID must differ from the original."
            )
            return
        template = draft_from_npc(source).model_copy(
            update={"id": new_id, "name": f"Copy of {source.name}"}
        )
        dialog = NpcDialog(self, credentials=self._credentials, draft=template)
        dialog.setWindowTitle("Duplicate NPC")
        dialog.id_input.setEnabled(True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            draft = dialog.draft()
            create_npc(self._active_campaign.directory, draft)
            updated_campaign = load_campaign(self._active_campaign.directory)
        except ValueError as exc:
            QMessageBox.critical(self, "Duplicate NPC error", str(exc))
            return
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        new_row = next(
            index for index, npc in enumerate(updated_campaign.npcs) if npc.id == draft.id
        )
        self._npc_list.setCurrentRow(new_row)
        self.statusBar().showMessage(f"Duplicated NPC: {draft.name}")

    def _propose_npc_lore(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        proposed = propose_npc_lore(self._active_npc)
        if proposed is None:
            QMessageBox.information(
                self, "Propose public lore", "No public facts found in the NPC profile."
            )
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Review proposed public lore")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        visibility_input = QComboBox()
        visibility_input.addItems(["public", "restricted", "secret", "gm-only"])
        visibility_input.setCurrentText(proposed.visibility)
        form.addRow("Visibility", visibility_input)
        scopes_input = QLineEdit()
        scopes_input.setText(", ".join(proposed.scopes))
        scopes_input.setPlaceholderText("order-of-the-rose, western-border")
        form.addRow("Scopes", scopes_input)
        target_input = QLineEdit(proposed.id)
        form.addRow("Lore file", target_input)
        layout.addLayout(form)
        layout.addWidget(QLabel("Content"))
        editor = QTextEdit()
        editor.setPlainText(proposed.body)
        editor.setMinimumHeight(300)
        layout.addWidget(editor)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        save = QPushButton("Save as new lore")
        save.clicked.connect(dialog.accept)
        save.setDefault(True)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        lore_id = target_input.text().strip()
        if not lore_id:
            return
        updated = proposed.model_copy(
            update={
                "visibility": visibility_input.currentText(),
                "scopes": tuple(
                    s.strip() for s in scopes_input.text().strip().split(",") if s.strip()
                ),
                "body": editor.toPlainText().strip(),
            }
        )
        content = render_lore_file(updated)
        try:
            save_lore_proposal(
                self._active_campaign.directory,
                lore_id,
                content,
                reason=f"Proposed from {self._active_npc.name}",
            )
        except ValueError:
            reply = QMessageBox.question(
                self,
                "Lore file exists",
                "A lore file with that name already exists. Overwrite with this proposal?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                save_lore(
                    self._active_campaign.directory,
                    lore_id,
                    content,
                    reason=f"Proposed from {self._active_npc.name}",
                )
            except ValueError as exc:
                QMessageBox.critical(self, "Lore save error", str(exc))
                return
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        npc_row = next(
            index
            for index, npc in enumerate(updated_campaign.npcs)
            if npc.id == self._active_npc.id
        )
        self._npc_list.setCurrentRow(npc_row)
        sorted_lore = sorted(updated_campaign.lore)
        if lore_id in sorted_lore:
            self._lore_list.setCurrentRow(sorted_lore.index(lore_id))
        self.statusBar().showMessage(f"Proposed lore: {lore_id}")

    def _select_npc(self, row: int) -> None:
        if self._voice_session.active:
            self._player_input.setEnabled(False)
            self._gm_input.setEnabled(False)
            asyncio.create_task(self._voice_session.stop())
        if self._active_campaign is None or not 0 <= row < len(self._active_campaign.npcs):
            self._active_npc = None
        else:
            self._active_npc = self._active_campaign.npcs[row]
        self._edit_npc_button.setEnabled(self._active_npc is not None)
        self._duplicate_npc_button.setEnabled(self._active_npc is not None)
        self._propose_lore_button.setEnabled(self._active_npc is not None)
        if self._active_npc is None:
            self._npc_heading.setText("No NPC selected")
            self._knowledge_heading.setText("No NPC selected")
            self._profile.clear()
            self._knowledge_editor.clear()
            self._knowledge_editor.setEnabled(False)
            self._knowledge_append.clear()
            self._knowledge_append.setEnabled(False)
            self._save_knowledge_button.setEnabled(False)
            self._append_knowledge_button.setEnabled(False)
            self._spell_check_knowledge_button.setEnabled(False)
            self._start_button.setEnabled(False)
            self._inspect_button.setEnabled(False)
            self._session_notes_button.setEnabled(False)
            self._speak_as_npc_button.setEnabled(False)
            return
        self._npc_heading.setText(self._active_npc.name)
        self._knowledge_heading.setText(self._active_npc.name)
        self._profile.setMarkdown(self._active_npc.profile)
        self._knowledge_editor.setPlainText(self._active_npc.memory)
        self._knowledge_editor.setEnabled(True)
        self._knowledge_append.clear()
        self._knowledge_append.setEnabled(True)
        self._save_knowledge_button.setEnabled(True)
        self._append_knowledge_button.setEnabled(True)
        self._spell_check_knowledge_button.setEnabled(True)
        self._load_active_transcript()
        self._start_button.setEnabled(True)
        self._inspect_button.setEnabled(True)
        self._session_notes_button.setEnabled(True)
        self._speak_as_npc_button.setEnabled("gemini" in self._active_npc.voice.providers)

    def _replace_active_npc_memory(self, memory: str) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        updated_npc = self._active_npc.model_copy(update={"memory": memory})
        updated_npcs = tuple(
            updated_npc if npc.id == updated_npc.id else npc for npc in self._active_campaign.npcs
        )
        updated_campaign = self._active_campaign.model_copy(update={"npcs": updated_npcs})
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._active_campaign = updated_campaign
        self._active_npc = updated_npc
        self._knowledge_editor.setPlainText(memory)
        if self._voice_session.active:
            asyncio.create_task(self._voice_session.stop())
            self.statusBar().showMessage(
                "NPC knowledge saved; voice session stopped to reload context"
            )
        else:
            self.statusBar().showMessage(f"Saved knowledge for {updated_npc.name}")

    def _save_npc_knowledge(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        content = self._knowledge_editor.toPlainText()
        reason, accepted = QInputDialog.getText(
            self,
            "Save NPC knowledge",
            "Reason for this change (optional)",
        )
        if not accepted:
            return
        try:
            save_npc_knowledge(
                self._active_campaign.directory,
                self._active_npc.id,
                content,
                reason=reason,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "NPC knowledge save error", str(exc))
            return
        self._replace_active_npc_memory(content)

    def _append_npc_knowledge(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        addition = self._knowledge_append.toPlainText().strip()
        if not addition:
            return
        try:
            updated = append_npc_knowledge(
                self._active_campaign.directory, self._active_npc.id, addition
            )
        except ValueError as exc:
            QMessageBox.critical(self, "NPC knowledge append error", str(exc))
            return
        self._knowledge_append.clear()
        self._replace_active_npc_memory(updated)

    def _create_lore(self) -> None:
        if self._active_campaign is None:
            return
        lore_id, accepted = QInputDialog.getText(
            self,
            "Create lore entry",
            "File name relative to the lore folder (Markdown or text)",
            text="new-lore.md",
        )
        lore_id = lore_id.strip().replace("\\", "/")
        if not accepted or not lore_id:
            return
        title = Path(lore_id).stem.replace("-", " ").replace("_", " ").strip().title()
        content = f"# {title}\n\n"
        try:
            create_lore(self._active_campaign.directory, lore_id, content)
        except ValueError as exc:
            QMessageBox.critical(self, "Lore creation error", str(exc))
            return
        updated_lore = dict(self._active_campaign.lore)
        updated_lore[lore_id] = content
        updated_campaign = self._active_campaign.model_copy(update={"lore": updated_lore})
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._active_campaign = updated_campaign
        self._lore_filter.clear()
        self._load_lore_list(select_id=lore_id)
        self._lore_editor.setFocus()
        if self._voice_session.active:
            asyncio.create_task(self._voice_session.stop())
            self.statusBar().showMessage(
                "Lore entry created; voice session stopped to reload context"
            )
        else:
            self.statusBar().showMessage(f"Created lore: {lore_id}")

    def _select_lore(self, row: int) -> None:
        if self._active_campaign is None:
            self._active_lore_id = None
        else:
            item = self._lore_list.item(row)
            self._active_lore_id = item.text() if item is not None else None
        if self._active_lore_id is None or self._active_campaign is None:
            self._lore_editor.clear()
            self._lore_editor.setEnabled(False)
            self._save_lore_button.setEnabled(False)
            return
        self._lore_editor.setPlainText(self._active_campaign.lore[self._active_lore_id])
        self._lore_editor.setEnabled(True)
        self._save_lore_button.setEnabled(True)
        self._spell_check_button.setEnabled(True)

    def _load_lore_list(self, select_id: str | None = None) -> None:
        if self._active_campaign is None:
            self._lore_list.clear()
            return
        query = self._lore_filter.text().lower().strip()
        self._lore_list.clear()
        for lore_id in sorted(self._active_campaign.lore):
            text = self._active_campaign.lore[lore_id].lower()
            if not query or query in lore_id.lower() or query in text:
                self._lore_list.addItem(lore_id)
        if select_id is not None:
            for row in range(self._lore_list.count()):
                if self._lore_list.item(row).text() == select_id:
                    self._lore_list.setCurrentRow(row)
                    return
        if self._lore_list.count():
            self._lore_list.setCurrentRow(0)

    def _save_lore(self) -> None:
        if self._active_campaign is None or self._active_lore_id is None:
            return
        content = self._lore_editor.toPlainText()
        reason, accepted = QInputDialog.getText(
            self,
            "Save lore",
            "Reason for this change (optional)",
        )
        if not accepted:
            return
        try:
            save_lore(
                self._active_campaign.directory,
                self._active_lore_id,
                content,
                reason=reason,
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Lore save error", str(exc))
            return
        updated_lore = dict(self._active_campaign.lore)
        updated_lore[self._active_lore_id] = content
        updated_campaign = self._active_campaign.model_copy(update={"lore": updated_lore})
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._active_campaign = updated_campaign
        if self._voice_session.active:
            asyncio.create_task(self._voice_session.stop())
            self.statusBar().showMessage("Lore saved; voice session stopped to reload context")
        else:
            self.statusBar().showMessage(f"Saved lore: {self._active_lore_id}")
        self._load_lore_list(select_id=self._active_lore_id)

    def _insert_lore_snippet(self, snippet: str) -> None:
        if not self._lore_editor.isEnabled():
            return
        self._lore_editor.textCursor().insertText(snippet)
        self._lore_editor.setFocus()

    def _insert_lore_scope(self) -> None:
        if not self._lore_editor.isEnabled():
            return
        scope = self._lore_scope_input.text().strip()
        if not scope:
            return
        self._lore_editor.textCursor().insertText(f"<!-- scope: {scope} -->\n")
        self._lore_scope_input.clear()
        self._lore_editor.setFocus()

    def _spell_check_lore(self) -> None:
        if self._active_campaign is None:
            return
        self._run_spell_check(self._lore_editor.toPlainText())

    def _spell_check_knowledge(self) -> None:
        if self._active_campaign is None:
            return
        self._run_spell_check(self._knowledge_editor.toPlainText())

    def _spell_check_speaker(self) -> None:
        if self._active_campaign is None:
            return
        self._run_spell_check(self._speaker_editor.toPlainText())

    def _run_spell_check(self, text: str) -> None:
        if self._active_campaign is None:
            return
        checker = CampaignSpellCheck(self._active_campaign.dictionary)
        unknown = checker.unknown(text)
        if not unknown:
            QMessageBox.information(self, "Spell check", "No unknown words found.")
            return
        SpellCheckDialog(self._active_campaign.directory, unknown, checker, self).exec()
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)

    def _load_active_transcript(self) -> None:
        self._transcript.clear()
        if self._active_campaign is None or self._active_npc is None:
            return
        for entry in load_transcript(self._active_campaign.directory, self._active_npc.id):
            self._append_transcript_display(entry.speaker, entry.text, private=entry.private)

    def _append_transcript_display(
        self, speaker: str, text: str, *, private: bool = False
    ) -> None:
        label = (
            "GM request (private)"
            if speaker == "gm request"
            else "GM instruction (private)"
            if private
            else speaker.capitalize()
        )
        value = f"<i>{html.escape(text)}</i>" if private else html.escape(text)
        self._transcript.append(f"<b>{html.escape(label)}:</b> {value}")

    def _show_transcript_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        promote_lore = menu.addAction("Promote to lore")
        promote_memory = menu.addAction("Promote to memory")
        action = menu.exec(self._transcript.mapToGlobal(pos))
        if action == promote_lore:
            self._promote_to_lore()
        elif action == promote_memory:
            self._promote_to_memory()

    def _promote_to_memory(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        snippet = self._transcript.textCursor().selectedText()
        if not snippet.strip():
            cursor = self._transcript.textCursor()
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            snippet = cursor.selectedText()
        snippet = snippet.replace("\u2029", "\n").strip()
        if not snippet:
            return
        try:
            append_npc_knowledge(
                self._active_campaign.directory,
                self._active_npc.id,
                snippet,
                reason="Promoted from transcript",
            )
        except ValueError as exc:
            QMessageBox.critical(self, "Memory append error", str(exc))
            return
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        self._npc_list.setCurrentRow(
            next(
                index
                for index, npc in enumerate(updated_campaign.npcs)
                if npc.id == self._active_npc.id
            )
        )
        self.statusBar().showMessage("Promoted selection to NPC memory")

    def _promote_to_lore(self) -> None:
        if self._active_campaign is None:
            return
        cursor = self._transcript.textCursor()
        snippet = cursor.selectedText()
        if not snippet.strip():
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            snippet = cursor.selectedText()
        snippet = snippet.replace("\u2029", "\n").strip()
        if not snippet:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Promote to lore")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Lore content"))
        editor = QTextEdit()
        editor.setPlainText(snippet)
        layout.addWidget(editor, 3)
        layout.addWidget(QLabel("Lore file name"))
        name_input = QLineEdit()
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        name_input.setText(f"curation-{stamp}.md")
        layout.addWidget(name_input)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        create = QPushButton("Create lore")
        create.clicked.connect(dialog.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        layout.addLayout(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        lore_id = name_input.text().strip().replace("\\", "/")
        if not lore_id:
            return
        content = editor.toPlainText().strip()
        if not content:
            return
        try:
            create_lore(self._active_campaign.directory, lore_id, f"{content}\n")
        except ValueError as exc:
            QMessageBox.critical(self, "Lore creation error", str(exc))
            return
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        self._lore_list.setCurrentRow(sorted(updated_campaign.lore).index(lore_id))
        self.statusBar().showMessage(f"Created lore: {lore_id}")

    def _save_transcript(self, speaker: str, text: str, *, private: bool = False) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        append_transcript(
            self._active_campaign.directory,
            self._active_npc.id,
            speaker,
            text,
            private=private,
        )
        if self._recording_session_id is not None:
            append_transcript(
                self._active_campaign.directory,
                self._recording_session_id,
                speaker,
                text,
                private=private,
            )
        self._append_transcript_display(speaker, text, private=private)

    def _toggle_session_recording(self) -> None:
        if self._active_campaign is None:
            return
        if self._recording_session_id is not None:
            self._recording_session_id = None
            self._record_button.setText("Record session")
            self._stop_session_button.setEnabled(False)
            self.statusBar().showMessage("Session recording stopped")
            self._load_session_list()
            if self._session_list.count():
                self._session_list.setCurrentRow(self._session_list.count() - 1)
            return
        session_id, accepted = QInputDialog.getText(
            self,
            "Record session",
            "Session ID (used for the filename)",
            text=f"table-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        )
        if not accepted or not session_id.strip():
            return
        session_id = session_id.strip().replace("\\", "/").replace(" ", "-")
        if session_id.endswith(".jsonl"):
            session_id = session_id[: -len(".jsonl")]
        if not session_id.startswith("table-"):
            session_id = "table-" + session_id
        self._recording_session_id = session_id
        self._record_button.setText("Stop recording")
        self._stop_session_button.setEnabled(True)
        self._load_session_list()
        self._session_list.setCurrentRow(
            next(
                (
                    i
                    for i in range(self._session_list.count())
                    if self._session_list.item(i).text() == self._recording_session_id
                ),
                0,
            )
        )
        self.statusBar().showMessage(f"Recording session: {self._recording_session_id}")

    def _send_player_text(self) -> None:
        text = self._player_input.text().strip()
        if not text:
            return
        self._save_transcript("player", text)
        self._player_input.clear()
        if self._voice_session.active:
            asyncio.create_task(self._voice_session.send_player_text(text))

    def _send_gm_text(self) -> None:
        text = self._gm_input.text().strip()
        if not text:
            return
        request_response = self._gm_request_response.isChecked()
        speaker = "gm request" if request_response else "gm"
        self._save_transcript(speaker, text, private=True)
        self._gm_input.clear()
        if self._voice_session.active:
            asyncio.create_task(
                self._voice_session.send_gm_instruction(text, request_response=request_response)
            )

    def _on_speak_as_npc(self) -> None:
        if self._active_npc is None:
            return
        try:
            api_key = self._credentials.get_gemini_api_key()
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        if not api_key:
            QMessageBox.information(
                self,
                "Gemini API key required",
                "Store a Gemini API key before using text-to-speech.",
            )
            return
        gemini = self._active_npc.voice.providers.get("gemini")
        if gemini is None:
            QMessageBox.information(
                self,
                "No Gemini voice",
                "This NPC has no Gemini voice configured. Edit the NPC and choose a voice.",
            )
            return
        text, accepted = QInputDialog.getMultiLineText(
            self,
            "Speak as NPC",
            f"Text to speak in {self._active_npc.name}'s voice:",
        )
        if not accepted or not text.strip():
            return
        self._speak_as_npc_button.setEnabled(False)
        self._speak_as_npc_button.setText("Speaking…")
        asyncio.create_task(self._speak_as_npc_text(api_key, gemini.voice, text.strip()))

    async def _speak_as_npc_text(self, api_key: str, voice: str, text: str) -> None:
        try:
            if self._active_npc is None:
                return
            style = self._active_npc.voice.style
            for mood, segment in tts_segments(text):
                await preview_voice(api_key, voice, mood, style, text=segment)
        except Exception as exc:
            QMessageBox.critical(self, "TTS error", str(exc))
        finally:
            self._speak_as_npc_button.setEnabled(True)
            self._speak_as_npc_button.setText("Speak as NPC")

    def _inspect_npc_context(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        inclusions = explain_npc_lore(self._active_campaign, self._active_npc)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Context for {self._active_npc.name}")
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        if inclusions:
            lines = [
                f"{inc.lore_id} — {inc.title} ({inc.visibility})\nReason: {inc.reason}"
                for inc in inclusions
            ]
            text.setPlainText("\n\n".join(lines))
        else:
            text.setPlainText("No eligible campaign lore for this NPC.")
        layout.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.resize(600, 400)
        dialog.exec()

    def _on_generate_session_notes(self) -> None:
        asyncio.create_task(self._generate_session_notes())

    async def _generate_session_notes(self) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        try:
            api_key = self._credentials.get_gemini_api_key()
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        if not api_key:
            QMessageBox.information(
                self,
                "Gemini API key required",
                "Store a Gemini API key from the main window before generating session notes.",
            )
            return
        self._session_notes_button.setEnabled(False)
        self._session_notes_button.setText("Summarizing…")
        try:
            entries = load_transcript(self._active_campaign.directory, self._active_npc.id)
            notes = await propose_session_notes(api_key, entries)
        except Exception as exc:
            QMessageBox.critical(self, "Session notes error", str(exc))
            return
        finally:
            self._session_notes_button.setEnabled(True)
            self._session_notes_button.setText("Generate session notes")
        self._show_session_notes_dialog(notes)

    def _show_session_notes_dialog(self, notes: SessionNotes) -> None:
        if self._active_campaign is None or self._active_npc is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Session notes")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Summary"))
        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setPlainText(notes.summary)
        layout.addWidget(summary)
        layout.addWidget(QLabel("Proposed memory"))
        memory = QTextEdit()
        memory.setReadOnly(True)
        memory.setPlainText(notes.proposed_memory)
        layout.addWidget(memory)
        if notes.proposed_lore:
            layout.addWidget(QLabel("Proposed lore (edit before creating)"))
            lore_editor = QTextEdit()
            lore_editor.setPlainText(
                "# Session-derived lore\n\n"
                + "\n".join(f"- {item}" for item in notes.proposed_lore)
            )
            layout.addWidget(lore_editor)
            create_lore = QPushButton("Create session lore")
            create_lore.clicked.connect(lambda: self._save_session_lore(lore_editor.toPlainText()))
            lore_buttons = QHBoxLayout()
            lore_buttons.addWidget(create_lore)
            lore_buttons.addStretch()
            layout.addLayout(lore_buttons)
        buttons = QHBoxLayout()
        append = QPushButton("Append memory to NPC")
        append.clicked.connect(dialog.accept)
        close = QPushButton("Close")
        close.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(append)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if notes.proposed_memory:
            try:
                append_npc_knowledge(
                    self._active_campaign.directory,
                    self._active_npc.id,
                    notes.proposed_memory,
                    reason="Generated from session notes",
                )
            except ValueError as exc:
                QMessageBox.critical(self, "Memory append error", str(exc))
                return
            updated_campaign = load_campaign(self._active_campaign.directory)
            campaign_index = self._campaigns.index(self._active_campaign)
            campaigns = list(self._campaigns)
            campaigns[campaign_index] = updated_campaign
            self._campaigns = tuple(campaigns)
            self._select_campaign(campaign_index)
            npc_row = next(
                index
                for index, npc in enumerate(updated_campaign.npcs)
                if npc.id == self._active_npc.id
            )
            self._npc_list.setCurrentRow(npc_row)
            self.statusBar().showMessage(f"Appended {len(notes.proposed_memory)} bytes to memory")

    def _save_session_lore(self, content: str) -> None:
        if self._active_campaign is None:
            return
        npc_id = self._active_npc.id if self._active_npc is not None else "session"
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        default = f"session-proposed/{npc_id}-{stamp}.md"
        lore_id, accepted = QInputDialog.getText(
            self,
            "Create session lore",
            "File name relative to the lore folder",
            text=default,
        )
        if not accepted or not lore_id.strip():
            return
        lore_id = lore_id.strip().replace("\\", "/")
        try:
            create_lore(self._active_campaign.directory, lore_id, content)
        except ValueError as exc:
            QMessageBox.critical(self, "Lore creation error", str(exc))
            return
        updated_campaign = load_campaign(self._active_campaign.directory)
        campaign_index = self._campaigns.index(self._active_campaign)
        campaigns = list(self._campaigns)
        campaigns[campaign_index] = updated_campaign
        self._campaigns = tuple(campaigns)
        self._select_campaign(campaign_index)
        self._lore_filter.clear()
        self._load_lore_list(select_id=lore_id)
        self._lore_editor.setFocus()
        if self._voice_session.active:
            asyncio.create_task(self._voice_session.stop())
            self.statusBar().showMessage(
                "Created session lore; voice session stopped to reload context"
            )
        else:
            self.statusBar().showMessage(f"Created session lore: {lore_id}")

    def _configure_gemini_key(self) -> None:
        key, accepted = QInputDialog.getText(
            self,
            "Gemini API key",
            "API key (stored in the operating-system keyring)",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return
        try:
            self._credentials.set_gemini_api_key(key)
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        self.statusBar().showMessage("Gemini API key saved securely")

    def _toggle_voice_session(self) -> None:
        if self._voice_session.active:
            asyncio.create_task(self._voice_session.stop())
            return
        if self._active_campaign is None or self._active_npc is None:
            return
        try:
            api_key = self._credentials.get_gemini_api_key()
        except ValueError as exc:
            QMessageBox.critical(self, "Credential error", str(exc))
            return
        if not api_key:
            QMessageBox.information(
                self,
                "Gemini API key required",
                "Select Gemini API key and store a credential before starting a session.",
            )
            return
        asyncio.create_task(
            self._voice_session.start(self._active_campaign, self._active_npc, api_key)
        )

    def _voice_state_changed(self, state: str) -> None:
        self._start_button.setText(
            "Stop voice session" if state == "active" else "Start voice session"
        )
        controls_enabled = state != "connecting" and self._active_npc is not None
        self._start_button.setEnabled(controls_enabled)
        self._player_input.setEnabled(controls_enabled)
        self._gm_input.setEnabled(controls_enabled)
        self.statusBar().showMessage(f"Voice session: {state}")

    def _receive_transcription(self, text: str, role: str, is_final: bool) -> None:
        if not is_final or not text.strip():
            return
        speaker = "player" if role == "user" else "npc"
        self._save_transcript(speaker, text)

    def _voice_error(self, message: str) -> None:
        QMessageBox.critical(self, "Voice session error", message)
