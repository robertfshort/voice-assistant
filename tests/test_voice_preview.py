from voice_assistant.services.voice_preview import tts_segments


def test_tts_segments_split_by_mood_tags() -> None:
    text = "Hello there. [[whisper]] Tell me more. [[normal]] Thank you."
    segments = tts_segments(text)
    assert segments == [
        ("", "Hello there."),
        ("whisper", "Tell me more."),
        ("", "Thank you."),
    ]


def test_tts_segments_preserves_mood_until_next_tag() -> None:
    text = "[[nervously]] I did not see anything. And you should not either."
    segments = tts_segments(text)
    assert segments == [
        ("nervously", "I did not see anything. And you should not either."),
    ]


def test_tts_segments_supports_closing_tags() -> None:
    text = "Start  [[whisper]]  middle  [[/whisper]]  end"
    segments = tts_segments(text)
    assert segments == [
        ("", "Start"),
        ("whisper", "middle"),
        ("", "end"),
    ]
