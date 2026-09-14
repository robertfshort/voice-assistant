from pathlib import Path

from voice_assistant.storage.voices import load_voice_registry, resolve_registered_voice


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


def test_missing_voice_registry_is_empty(tmp_path: Path) -> None:
    assert load_voice_registry(tmp_path).piper == {}
    assert resolve_registered_voice("missing", tmp_path) is None
