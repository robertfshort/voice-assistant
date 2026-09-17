from types import SimpleNamespace

import numpy as np
from pytest import MonkeyPatch

from voice_assistant.services import session_audio as session_audio_module


def test_session_audio_recorder_writes_wav_file(tmp_path, monkeypatch: MonkeyPatch) -> None:
    captured = {}

    class FakeStream:
        def __init__(self, **kwargs: object) -> None:
            captured["callback"] = kwargs["callback"]
            self.stopped = True

        def start(self) -> None:
            self.stopped = False

        def stop(self) -> None:
            self.stopped = True

        def close(self) -> None:
            pass

    fake_sounddevice = SimpleNamespace(RawInputStream=FakeStream)

    def fake_import_module(name: str) -> object:
        if name == "sounddevice":
            return fake_sounddevice
        raise ImportError(name)

    monkeypatch.setattr(session_audio_module.importlib, "import_module", fake_import_module)

    recorder = session_audio_module.SessionAudioRecorder()
    recorder.start()
    assert recorder.is_recording

    fake_data = np.array([1, 2, 3, 4], dtype=np.int16)
    captured["callback"](fake_data, 4, None, None)

    output_path = tmp_path / "audio.wav"
    recorder.stop(output_path)

    assert output_path.is_file()
    with open(output_path, "rb") as stream:
        header = stream.read(4)
        assert header == b"RIFF"
