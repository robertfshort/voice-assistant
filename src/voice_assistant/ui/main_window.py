from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from voice_assistant.domain.models import Campaign, Npc
from voice_assistant.storage.campaigns import discover_campaigns


class MainWindow(QMainWindow):
    campaign_root_changed = Signal(Path)

    def __init__(self, campaign_root: Path) -> None:
        super().__init__()
        self._campaign_root = campaign_root
        self._campaigns: tuple[Campaign, ...] = ()
        self._active_campaign: Campaign | None = None
        self._active_npc: Npc | None = None
        self.setWindowTitle("RPG Voice Assistant")
        self.resize(1100, 720)
        self._build_ui()
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
        splitter.addWidget(selection)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        self._npc_heading = QLabel("No NPC selected")
        self._npc_heading.setStyleSheet("font-size: 20px; font-weight: 600;")
        workspace_layout.addWidget(self._npc_heading)
        self._profile = QTextEdit()
        self._profile.setReadOnly(True)
        workspace_layout.addWidget(self._profile, 2)

        workspace_layout.addWidget(QLabel("Conversation"))
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        workspace_layout.addWidget(self._transcript, 2)

        input_form = QFormLayout()
        self._player_input = QLineEdit()
        self._player_input.setPlaceholderText("In-character player dialogue")
        self._player_input.returnPressed.connect(self._send_player_text)
        self._gm_input = QLineEdit()
        self._gm_input.setPlaceholderText("Private out-of-character GM instruction")
        self._gm_input.returnPressed.connect(self._send_gm_text)
        input_form.addRow("Player says", self._player_input)
        input_form.addRow("GM directs", self._gm_input)
        workspace_layout.addLayout(input_form)

        controls = QHBoxLayout()
        self._start_button = QPushButton("Start voice session")
        self._start_button.setEnabled(False)
        player_button = QPushButton("Send player text")
        player_button.clicked.connect(self._send_player_text)
        gm_button = QPushButton("Send private GM instruction")
        gm_button.clicked.connect(self._send_gm_text)
        controls.addWidget(self._start_button)
        controls.addStretch()
        controls.addWidget(player_button)
        controls.addWidget(gm_button)
        workspace_layout.addLayout(controls)
        splitter.addWidget(workspace)
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
        self._profile.clear()
        self._npc_heading.setText("No NPC selected")
        for campaign in self._campaigns:
            self._campaign_list.addItem(campaign.manifest.name)
        if self._campaigns:
            self._campaign_list.setCurrentRow(0)
        self.statusBar().showMessage(f"Loaded {len(self._campaigns)} campaign(s)")

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
        self._npc_list.clear()
        if self._active_campaign is None:
            return
        for npc in self._active_campaign.npcs:
            self._npc_list.addItem(npc.name)
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

    def _select_npc(self, row: int) -> None:
        if self._active_campaign is None or not 0 <= row < len(self._active_campaign.npcs):
            self._active_npc = None
        else:
            self._active_npc = self._active_campaign.npcs[row]
        if self._active_npc is None:
            self._npc_heading.setText("No NPC selected")
            self._profile.clear()
            self._start_button.setEnabled(False)
            return
        self._npc_heading.setText(self._active_npc.name)
        self._profile.setMarkdown(self._active_npc.profile)
        self._start_button.setEnabled(True)

    def _send_player_text(self) -> None:
        text = self._player_input.text().strip()
        if not text:
            return
        self._transcript.append(f"<b>Player:</b> {text}")
        self._player_input.clear()

    def _send_gm_text(self) -> None:
        text = self._gm_input.text().strip()
        if not text:
            return
        self._transcript.append(f"<b>GM instruction (private):</b> <i>{text}</i>")
        self._gm_input.clear()
