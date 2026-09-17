from __future__ import annotations

import shutil
from pathlib import Path

import PyInstaller.__main__

PRODUCT_NAME = "RPG Voice Assistant Early Alpha"
REPOSITORY = Path(__file__).resolve().parent
OUTPUT_ROOT = REPOSITORY.parent / "Early Alpha"
BUNDLE = OUTPUT_ROOT / PRODUCT_NAME


def main() -> None:
    if OUTPUT_ROOT.exists():
        raise SystemExit(f"Release destination already exists: {OUTPUT_ROOT}")
    (REPOSITORY / "build").mkdir(exist_ok=True)
    PyInstaller.__main__.run(
        [
            "--name",
            PRODUCT_NAME,
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--distpath",
            str(OUTPUT_ROOT),
            "--workpath",
            str(REPOSITORY / "build" / "early-alpha"),
            "--specpath",
            str(REPOSITORY / "build"),
            "--collect-submodules=roomkit",
            "--collect-submodules=voice_assistant",
            "--collect-all=piper",
            "--copy-metadata=roomkit",
            "--copy-metadata=voice-assistant",
            "--hidden-import=google.genai",
            "--hidden-import=google.genai.live",
            "--hidden-import=websockets",
            "--hidden-import=sounddevice",
            "--hidden-import=_sounddevice_data",
            "--hidden-import=certifi",
            "--hidden-import=keyring.backends.Windows",
            str(REPOSITORY / "src" / "voice_assistant" / "__main__.py"),
        ]
    )
    shutil.copytree(REPOSITORY / "examples" / "campaigns", BUNDLE / "campaigns")
    shutil.copy2(REPOSITORY / "LICENSE", BUNDLE / "LICENSE.txt")
    (BUNDLE / "EARLY_ALPHA_README.txt").write_text(
        "RPG Voice Assistant — Early Alpha\n"
        "=================================\n\n"
        "Run 'RPG Voice Assistant Early Alpha.exe'. The included campaigns folder is used "
        "automatically.\n\n"
        "Requirements:\n"
        "- Windows 10 or 11, 64-bit\n"
        "- Internet access for Gemini features\n"
        "- A Gemini API key, entered through the application\n"
        "- A working default microphone and playback device\n\n"
        "This is an early alpha build. Back up campaign directories before editing them. "
        "API credentials are stored in Windows Credential Manager and are not included here.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
