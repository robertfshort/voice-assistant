from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from voice_assistant.storage.settings import (
    AppSettings,
    StorageSettings,
    load_settings,
    resolve_campaign_root,
    save_settings,
)
from voice_assistant.ui.main_window import MainWindow


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable tabletop RPG voice assistant")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--campaign-root", type=Path)
    parser.add_argument("--portable", action="store_true")
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    settings = load_settings(arguments.config)
    storage = settings.storage
    if arguments.campaign_root is not None or arguments.portable:
        storage = StorageSettings(
            campaign_root=arguments.campaign_root or storage.campaign_root,
            portable_mode=arguments.portable or storage.portable_mode,
        )
    campaign_root = resolve_campaign_root(storage)

    application = QApplication(sys.argv)
    application.setApplicationName("RPG Voice Assistant")
    application.setOrganizationName("RobertShort")
    window = MainWindow(campaign_root)

    def save_campaign_root(path: Path) -> None:
        updated = AppSettings(
            storage=StorageSettings(campaign_root=path, portable_mode=False),
            providers=settings.providers,
        )
        save_settings(updated, arguments.config)

    window.campaign_root_changed.connect(save_campaign_root)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
