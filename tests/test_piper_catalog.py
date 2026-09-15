import asyncio
import hashlib
import json
from collections.abc import Coroutine
from dataclasses import replace
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx
from PySide6.QtWidgets import QAbstractItemView
from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

from voice_assistant.services import piper_catalog
from voice_assistant.ui import piper_catalog_dialog
from voice_assistant.ui.piper_catalog_dialog import PiperCatalogDialog


def _catalog() -> dict[str, object]:
    return {
        "en_US-test-medium": {
            "key": "en_US-test-medium",
            "name": "test",
            "language": {
                "code": "en_US",
                "name_english": "English",
                "country_english": "United States",
            },
            "quality": "medium",
            "num_speakers": 2,
            "files": {
                "en/en_US/test/medium/en_US-test-medium.onnx": {
                    "size_bytes": 1048576,
                    "md5_digest": "model-digest",
                },
                "en/en_US/test/medium/en_US-test-medium.onnx.json": {
                    "size_bytes": 1024,
                    "md5_digest": "config-digest",
                },
                "en/en_US/test/medium/MODEL_CARD": {
                    "size_bytes": 100,
                    "md5_digest": "card-digest",
                },
            },
        }
    }


class _OfflineClient:
    async def __aenter__(self) -> "_OfflineClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get(self, url: str) -> object:
        raise httpx.ConnectError("offline")


def test_portable_voice_name_removes_unsafe_path_characters() -> None:
    assert piper_catalog.portable_voice_name("../../en_US/test") == "en-us-test"


def test_parse_catalog_extracts_download_metadata() -> None:
    voice = piper_catalog.parse_catalog(_catalog())[0]

    assert voice.key == "en_US-test-medium"
    assert voice.language == "English"
    assert voice.country == "United States"
    assert voice.quality == "medium"
    assert voice.speakers == 2
    assert voice.size_bytes == 1049600
    assert voice.model_digest == "model-digest"
    assert voice.model_card_path.endswith("MODEL_CARD")


def test_catalog_uses_cached_metadata_when_offline(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "catalog.json").write_text(json.dumps(_catalog()), encoding="utf-8")
    monkeypatch.setattr(piper_catalog.httpx, "AsyncClient", lambda **kwargs: _OfflineClient())

    voices = asyncio.run(piper_catalog.fetch_piper_catalog(cache))

    assert voices[0].key == "en_US-test-medium"


def test_model_card_uses_cached_metadata_when_offline(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    voice = piper_catalog.parse_catalog(_catalog())[0]
    cache = tmp_path / "cache"
    model_cards = cache / "model-cards"
    model_cards.mkdir(parents=True)
    cache_name = hashlib.sha256(voice.key.encode("utf-8")).hexdigest() + ".md"
    (model_cards / cache_name).write_text("* License: MIT\n", encoding="utf-8")
    monkeypatch.setattr(piper_catalog.httpx, "AsyncClient", lambda **kwargs: _OfflineClient())

    card = asyncio.run(piper_catalog.fetch_model_card(voice, cache))

    assert card.license == "MIT"


def test_parse_model_card_extracts_license() -> None:
    card = piper_catalog.parse_model_card("## Dataset\n\n* License: CC-BY-4.0\n")

    assert card.license == "CC-BY-4.0"


def test_download_voice_verifies_then_registers_assets(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    voice = piper_catalog.parse_catalog(_catalog())[0]

    def fake_download(
        client: object,
        relative: str,
        target: Path,
        digest: str,
        expected_size: int,
        progress: object,
    ) -> None:
        target.write_text(relative + digest, encoding="utf-8")

    monkeypatch.setattr(piper_catalog, "_download_file", fake_download)

    registered = asyncio.run(piper_catalog.download_piper_voice(voice, tmp_path))

    assert registered == "en-us-test-medium"
    registry = (tmp_path / "voices.yaml").read_text(encoding="utf-8")
    assert "en-us-test-medium" in registry
    assert (tmp_path / "piper" / registered / "en_US-test-medium.onnx").is_file()


def test_catalog_dialog_supports_selecting_multiple_voices(
    tmp_path: Path, qtbot: QtBot, monkeypatch: MonkeyPatch
) -> None:
    def discard_task(coroutine: Coroutine[Any, Any, Any]) -> None:
        coroutine.close()

    monkeypatch.setattr(piper_catalog_dialog.asyncio, "create_task", discard_task)
    voice = piper_catalog.parse_catalog(_catalog())[0]
    dialog = PiperCatalogDialog(tmp_path)
    qtbot.addWidget(dialog)
    dialog._voices = (voice, replace(voice, key="en_US-second-medium", name="second"))
    dialog._refresh()
    dialog.voice_list.item(0).setSelected(True)
    dialog.voice_list.item(1).setSelected(True)

    assert dialog.voice_list.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert [selected.key for selected in dialog._selected_voices()] == [
        "en_US-test-medium",
        "en_US-second-medium",
    ]
    assert dialog.download_button.text() == "Download and register 2 voices"
