from __future__ import annotations

GEMINI_VOICE_GENDERS: dict[str, str] = {
    "Achernar": "Female",
    "Achird": "Male",
    "Algenib": "Male",
    "Algieba": "Male",
    "Alnilam": "Male",
    "Aoede": "Female",
    "Autonoe": "Female",
    "Callirrhoe": "Female",
    "Charon": "Male",
    "Despina": "Female",
    "Enceladus": "Male",
    "Erinome": "Female",
    "Fenrir": "Male",
    "Gacrux": "Female",
    "Iapetus": "Male",
    "Kore": "Female",
    "Laomedeia": "Female",
    "Leda": "Female",
    "Orus": "Male",
    "Pulcherrima": "Female",
    "Puck": "Male",
    "Rasalgethi": "Male",
    "Sadachbia": "Male",
    "Sadaltager": "Male",
    "Schedar": "Male",
    "Sulafat": "Female",
    "Umbriel": "Male",
    "Vindemiatrix": "Female",
    "Zephyr": "Female",
    "Zubenelgenubi": "Male",
}

GEMINI_VOICES: tuple[str, ...] = tuple(sorted(GEMINI_VOICE_GENDERS))
GEMINI_GENDERS: tuple[str, ...] = ("Female", "Male")


def voices_for_gender(gender: str) -> list[str]:
    return sorted(
        voice for voice, voice_gender in GEMINI_VOICE_GENDERS.items() if voice_gender == gender
    )


def gender_for_voice(voice: str) -> str:
    return GEMINI_VOICE_GENDERS.get(voice, "Female")
