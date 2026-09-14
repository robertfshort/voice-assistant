from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from voice_assistant.storage.settings import (
    AppearanceSettings,
    AppSettings,
    StorageSettings,
    load_settings,
    resolve_campaign_root,
    save_settings,
)
from voice_assistant.ui.main_window import MainWindow
from voice_assistant.ui.themes import apply_theme


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
    frozen_portable = (
        getattr(sys, "frozen", False)
        and arguments.campaign_root is None
        and storage.campaign_root is None
    )
    if arguments.campaign_root is not None or arguments.portable or frozen_portable:
        storage = StorageSettings(
            campaign_root=arguments.campaign_root or storage.campaign_root,
            portable_mode=arguments.portable or frozen_portable or storage.portable_mode,
        )
    campaign_root = resolve_campaign_root(storage)

    application = QApplication(sys.argv)
    application.setApplicationName("RPG Voice Assistant")
    application.setOrganizationName("RobertShort")
    apply_theme(settings.appearance.theme, target=application)
    window = MainWindow(campaign_root, theme=settings.appearance.theme)

    def save_campaign_root(path: Path) -> None:
        updated = AppSettings(
            storage=StorageSettings(campaign_root=path, portable_mode=False),
            providers=settings.providers,
            appearance=settings.appearance,
        )
        save_settings(updated, arguments.config)

    def save_theme(name: str) -> None:
        updated = AppSettings(
            storage=settings.storage,
            providers=settings.providers,
            appearance=AppearanceSettings(theme=name),
        )
        save_settings(updated, arguments.config)

    window.campaign_root_changed.connect(save_campaign_root)
    window.theme_changed.connect(save_theme)
    window.show()
    event_loop = QEventLoop(application)
    asyncio.set_event_loop(event_loop)
    application.aboutToQuit.connect(event_loop.stop)
    with event_loop:
        event_loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
