from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from voice_assistant.storage.settings import (
    AppearanceSettings,
    ProviderSettings,
    SpeechSettings,
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
    window = MainWindow(
        campaign_root,
        theme=settings.appearance.theme,
        providers=settings.providers,
        speech=settings.speech,
    )
    current_settings = settings.model_copy(update={"storage": storage})

    def persist(**updates: object) -> None:
        nonlocal current_settings
        current_settings = current_settings.model_copy(update=updates)
        save_settings(current_settings, arguments.config)

    def save_campaign_root(path: Path) -> None:
        persist(storage=StorageSettings(campaign_root=path, portable_mode=False))

    def save_theme(name: str) -> None:
        persist(appearance=AppearanceSettings(theme=name))

    def save_tts(providers: ProviderSettings, speech: SpeechSettings) -> None:
        persist(providers=providers, speech=speech)

    window.campaign_root_changed.connect(save_campaign_root)
    window.theme_changed.connect(save_theme)
    window.tts_settings_changed.connect(save_tts)
    window.show()
    event_loop = QEventLoop(application)
    asyncio.set_event_loop(event_loop)
    application.aboutToQuit.connect(event_loop.stop)
    with event_loop:
        event_loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
