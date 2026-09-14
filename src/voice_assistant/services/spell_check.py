from __future__ import annotations

import re
from collections.abc import Iterable

from spellchecker import SpellChecker

_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


class CampaignSpellCheck:
    def __init__(self, campaign_dictionary: Iterable[str] = ()) -> None:
        self._spell = SpellChecker()
        self._spell.word_frequency.load_words({w.lower() for w in campaign_dictionary})

    def unknown(self, text: str) -> list[str]:
        words = [w for w in _WORD.findall(text) if len(w) > 1]
        return sorted(set(self._spell.unknown([w.lower() for w in words])))

    def candidates(self, word: str) -> list[str]:
        found = self._spell.candidates(word.lower())
        if not found:
            return []
        return sorted(w for w in found if w.lower() != word.lower())[:5]

    def is_known(self, word: str) -> bool:
        return bool(self._spell.known([word.lower()]))
