import asyncio
from pathlib import Path

from pytest import MonkeyPatch

from voice_assistant.services import piper_catalog


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
