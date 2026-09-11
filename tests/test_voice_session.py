from voice_assistant.services.voice_session import VoiceSessionController


def test_voice_session_starts_inactive() -> None:
    controller = VoiceSessionController()

    assert controller.active is False
