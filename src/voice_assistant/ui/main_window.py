from __future__ import annotations

import asyncio
import html
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.domain.models import Campaign, Npc
from voice_assistant.services.voice_session import VoiceSessionController
from voice_assistant.storage.campaigns import discover_campaigns, load_campaign
from voice_assistant.storage.credentials import CredentialStore
from voice_assistant.storage.lore import create_lore, save_lore
from voice_assistant.storage.npc_creation import create_npc, draft_from_npc, update_npc
from voice_assistant.storage.npc_knowledge import append_npc_knowledge, save_npc_knowledge
from voice_assistant.storage.npc_lore_proposals import (
    propose_npc_lore,
    render_lore_file,
    save_lore_proposal,
)
from voice_assistant.storage.transcripts import append_transcript, load_transcript
from voice_assistant.ui.npc_dialog import NpcDialog
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
        self._active_lore_id: str | None = None
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
        path_row.addWidget(QLabel("Campaign root"))
        path_row.addWidget(self._campaign_path, 1)
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
        controls.addWidget(self._start_button)
        controls.addWidget(provider_button)
        controls.addStretch()
        controls.addWidget(player_button)
        controls.addWidget(gm_button)
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
        knowledge_controls.addStretch()
        knowledge_controls.addWidget(self._save_knowledge_button)
        knowledge_controls.addWidget(self._append_knowledge_button)
        knowledge_layout.addLayout(knowledge_controls)
        tabs.addTab(knowledge, "NPC knowledge")

        lore = QWidget()
        lore_layout = QVBoxLayout(lore)
        lore_layout.addWidget(QLabel("Campaign lore"))
        self._lore_list = QListWidget()
        self._lore_list.currentRowChanged.connect(self._select_lore)
        lore_layout.addWidget(self._lore_list, 1)
        self._lore_editor = QTextEdit()
        self._lore_editor.setPlaceholderText("Select a lore file to view or edit it")
        self._lore_editor.setEnabled(False)
        lore_layout.addWidget(self._lore_editor, 3)
        lore_controls = QHBoxLayout()
        self._new_lore_button = QPushButton("Create lore entry")
        self._new_lore_button.setEnabled(False)
        self._new_lore_button.clicked.connect(self._create_lore)
        self._save_lore_button = QPushButton("Save lore")
        self._save_lore_button.setEnabled(False)
        self._save_lore_button.clicked.connect(self._save_lore)
        lore_controls.addStretch()
        lore_controls.addWidget(self._new_lore_button)
        lore_controls.addWidget(self._save_lore_button)
        lore_layout.addLayout(lore_controls)
        tabs.addTab(lore, "Lore")

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
        self._new_lore_button.setEnabled(False)
        self._active_lore_id = None
        self._profile.clear()
        self._knowledge_editor.clear()
        self._knowledge_editor.setEnabled(False)
        self._knowledge_append.clear()
        self._knowledge_append.setEnabled(False)
        self._save_knowledge_button.setEnabled(False)
        self._append_knowledge_button.setEnabled(False)
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
            "Choose campaign root",
            str(self._campaign_root),
        )
        if selected:
            path = Path(selected)
            self.load_campaign_root(path)
            self.campaign_root_changed.emit(path)

    def _select_campaign(self, row: int) -> None:
        self._active_campaign = self._campaigns[row] if 0 <= row < len(self._campaigns) else None
        self._active_npc = None
        self._active_lore_id = None
        self._npc_list.clear()
        self._lore_list.clear()
        self._lore_editor.clear()
        self._lore_editor.setEnabled(False)
        self._save_lore_button.setEnabled(False)
        self._add_npc_button.setEnabled(self._active_campaign is not None)
        self._new_lore_button.setEnabled(self._active_campaign is not None)
        if self._active_campaign is None:
            return
        for npc in self._active_campaign.npcs:
            self._npc_list.addItem(npc.name)
        for lore_id in sorted(self._active_campaign.lore):
            self._lore_list.addItem(lore_id)
        if self._lore_list.count():
            self._lore_list.setCurrentRow(0)
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
        self.statusBar().showMessage(f"Updated NPC: {draft.name}")

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
        layout.addWidget(QLabel("Content"))
        editor = QTextEdit()
        editor.setPlainText(render_lore_file(proposed))
        editor.setMinimumHeight(300)
        layout.addWidget(editor)
        layout.addWidget(QLabel("Lore file"))
        target_input = QLineEdit(proposed.id)
        layout.addWidget(target_input)
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
        content = editor.toPlainText()
        if not lore_id:
            return
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
            self._start_button.setEnabled(False)
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
        self._load_active_transcript()
        self._start_button.setEnabled(True)

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
        self._lore_list.clear()
        lore_ids = sorted(updated_lore)
        self._lore_list.addItems(lore_ids)
        self._lore_list.setCurrentRow(lore_ids.index(lore_id))
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
            lore_ids = sorted(self._active_campaign.lore)
            self._active_lore_id = lore_ids[row] if 0 <= row < len(lore_ids) else None
        if self._active_lore_id is None or self._active_campaign is None:
            self._lore_editor.clear()
            self._lore_editor.setEnabled(False)
            self._save_lore_button.setEnabled(False)
            return
        self._lore_editor.setPlainText(self._active_campaign.lore[self._active_lore_id])
        self._lore_editor.setEnabled(True)
        self._save_lore_button.setEnabled(True)

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
        self._append_transcript_display(speaker, text, private=private)

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
