from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from voice_assistant.ui.themes import THEME_NAMES, apply_theme, valid_theme


def test_themes_include_requested_set() -> None:
    assert set(THEME_NAMES) == {"light", "dark", "dungeon", "tavern"}


def test_valid_theme_recognizes_known_names_and_rejects_unknown() -> None:
    assert valid_theme("dungeon") is True
    assert valid_theme("tavern") is True
    assert valid_theme("not-a-theme") is False


def test_apply_theme_sets_stylesheet_on_target(qtbot: QtBot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    apply_theme("tavern", target=widget)

    stylesheet = widget.styleSheet()
    assert "#2b211b" in stylesheet
    assert "#8b5a2b" in stylesheet
