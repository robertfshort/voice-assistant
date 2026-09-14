from pathlib import Path

import pytest

from voice_assistant.domain.errors import ConfigurationError
from voice_assistant.storage.voices import (
    import_piper_voice,
    load_voice_registry,
    remove_piper_voice,
    resolve_registered_voice,
)


def test_load_and_resolve_registered_piper_voice(tmp_path: Path) -> None:
    (tmp_path / "voices.yaml").write_text(
        "piper:\n  innkeeper:\n    model: piper/innkeeper.onnx\n"
        "    config: piper/innkeeper.onnx.json\n",
        encoding="utf-8",
    )

    registry = load_voice_registry(tmp_path)
    resolved = resolve_registered_voice("innkeeper", tmp_path)

    assert registry.piper["innkeeper"].model == "piper/innkeeper.onnx"
    assert resolved == (
        (tmp_path / "piper" / "innkeeper.onnx").resolve(),
        (tmp_path / "piper" / "innkeeper.onnx.json").resolve(),
    )


def test_import_piper_voice_copies_assets_and_updates_registry(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    model = source / "mara.onnx"
    config = source / "mara.onnx.json"
    model.write_bytes(b"model")
    config.write_text("{}", encoding="utf-8")
    root = tmp_path / "voices"

    import_piper_voice(root, "mara", model, config)

    resolved = resolve_registered_voice("mara", root)
    assert resolved is not None
    assert resolved[0].read_bytes() == b"model"
    assert resolved[1] is not None
    assert resolved[1].read_text(encoding="utf-8") == "{}"


def test_remove_piper_voice_updates_registry_and_deletes_assets(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    model = source / "mara.onnx"
    config = source / "mara.onnx.json"
    model.write_bytes(b"model")
    config.write_text("{}", encoding="utf-8")
    root = tmp_path / "voices"
    import_piper_voice(root, "mara", model, config)
    installed = resolve_registered_voice("mara", root)
    assert installed is not None

    remove_piper_voice(root, "mara")

    assert resolve_registered_voice("mara", root) is None
    assert not installed[0].exists()
    assert installed[1] is not None
    assert not installed[1].exists()


def test_registered_voice_cannot_escape_voice_root(tmp_path: Path) -> None:
    (tmp_path / "voices.yaml").write_text(
        "piper:\n  unsafe:\n    model: ../outside.onnx\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="outside the voice folder"):
        resolve_registered_voice("unsafe", tmp_path)


def test_missing_voice_registry_is_empty(tmp_path: Path) -> None:
    assert load_voice_registry(tmp_path).piper == {}
    assert resolve_registered_voice("missing", tmp_path) is None
