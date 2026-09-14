from __future__ import annotations

from voice_assistant.services.spell_check import CampaignSpellCheck
from voice_assistant.storage.dictionary import (
    append_to_campaign_dictionary,
    load_campaign_dictionary,
)


def test_spell_check_finds_unknown_words() -> None:
    checker = CampaignSpellCheck()
    unknown = checker.unknown("The tavernkeepr has a sword.")
    assert "tavernkeepr" in unknown
    assert "sword" not in unknown


def test_campaign_dictionary_excludes_known_words() -> None:
    checker = CampaignSpellCheck(["elara", "voss"])
    unknown = checker.unknown("Elara Voss has a sword.")
    assert "elara" not in unknown
    assert "voss" not in unknown
    assert "sword" not in unknown


def test_load_and_save_campaign_dictionary(tmp_path) -> None:
    append_to_campaign_dictionary(tmp_path, ["Elara", "Lantern's"])
    words = load_campaign_dictionary(tmp_path)
    assert "elara" in words
    assert "lantern's" in words

    append_to_campaign_dictionary(tmp_path, ["Duggar"])
    words = load_campaign_dictionary(tmp_path)
    assert "duggar" in words


def test_candidates_provides_suggestions() -> None:
    checker = CampaignSpellCheck()
    candidates = checker.candidates("hte")
    assert candidates
