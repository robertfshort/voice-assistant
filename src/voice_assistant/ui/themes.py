from __future__ import annotations

from string import Template

from PySide6.QtWidgets import QApplication, QWidget

THEME_NAMES: tuple[str, ...] = ("light", "dark", "dungeon", "tavern")

_BASE_STYLESHEET = Template("""
QMainWindow, QDialog, QWidget {
    background-color: $background;
    color: $foreground;
}
QLabel, QLineEdit, QTextEdit, QComboBox, QListWidget, QTabWidget::pane, QTabBar::tab {
    color: $foreground;
    background-color: $background;
}
QPushButton {
    background-color: $accent;
    color: $button_text;
    border: 1px solid $border;
    padding: 4px 12px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: $accent_hover;
}
QPushButton:pressed {
    background-color: $accent_pressed;
}
QPushButton:disabled {
    color: $disabled;
    background-color: $disabled_background;
}
QLineEdit, QTextEdit, QComboBox, QListWidget {
    border: 1px solid $border;
    background-color: $input_background;
    color: $foreground;
}
QListWidget::item:selected {
    background-color: $accent;
    color: $button_text;
}
QListWidget::item:selected:!active {
    background-color: $border;
    color: $foreground;
}
QTabBar::tab:selected {
    background-color: $accent;
    color: $button_text;
}
QTabBar::tab:hover {
    background-color: $accent_hover;
}
QMenuBar, QMenu {
    background-color: $background;
    color: $foreground;
    border: 1px solid $border;
}
QMenu::item:selected {
    background-color: $accent;
    color: $button_text;
}
QMessageBox {
    background-color: $background;
    color: $foreground;
}
QInputDialog {
    background-color: $background;
    color: $foreground;
}
""")

_THEME_COLORS: dict[str, dict[str, str]] = {
    "light": {
        "background": "#ffffff",
        "foreground": "#1a1a1a",
        "input_background": "#ffffff",
        "accent": "#3a7a3a",
        "accent_hover": "#2d5f2d",
        "accent_pressed": "#204420",
        "button_text": "#ffffff",
        "border": "#b0b0b0",
        "disabled": "#808080",
        "disabled_background": "#e0e0e0",
    },
    "dark": {
        "background": "#2b2b2b",
        "foreground": "#eeeeee",
        "input_background": "#333333",
        "accent": "#5a9fd4",
        "accent_hover": "#4a8fc4",
        "accent_pressed": "#3a7fb4",
        "button_text": "#ffffff",
        "border": "#555555",
        "disabled": "#777777",
        "disabled_background": "#3b3b3b",
    },
    "dungeon": {
        "background": "#1a1a1a",
        "foreground": "#c0b0a0",
        "input_background": "#0f0f0f",
        "accent": "#7a2f2f",
        "accent_hover": "#6a2525",
        "accent_pressed": "#5a1b1b",
        "button_text": "#e0d0d0",
        "border": "#4a3a3a",
        "disabled": "#666666",
        "disabled_background": "#2b2020",
    },
    "tavern": {
        "background": "#2b211b",
        "foreground": "#f0e6d2",
        "input_background": "#3b2e24",
        "accent": "#8b5a2b",
        "accent_hover": "#7a4f26",
        "accent_pressed": "#6a4420",
        "button_text": "#f0e6d2",
        "border": "#6a4a32",
        "disabled": "#8a7a6a",
        "disabled_background": "#4b3a2e",
    },
}


def valid_theme(name: str) -> bool:
    return name in THEME_NAMES


def apply_theme(
    name: str, target: QApplication | QWidget | None = None
) -> None:
    if not valid_theme(name):
        raise ValueError(f"Unknown theme: {name!r}. Available: {', '.join(THEME_NAMES)}")
    widget = target or QApplication.instance()
    if not isinstance(widget, (QApplication, QWidget)):
        return
    widget.setStyleSheet(_BASE_STYLESHEET.substitute(_THEME_COLORS[name]))
