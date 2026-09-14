from __future__ import annotations

from pathlib import Path


def load_campaign_dictionary(directory: Path) -> tuple[str, ...]:
    path = directory / "dictionary.txt"
    if not path.exists():
        return ()
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.split("#", 1)[0].strip().lower()
        if word:
            words.append(word)
    return tuple(sorted(set(words)))


def append_to_campaign_dictionary(directory: Path, words: list[str]) -> None:
    path = directory / "dictionary.txt"
    existing = set(load_campaign_dictionary(directory))
    existing.update(w.strip().lower() for w in words if w.strip())
    text = "\n".join(sorted(existing)) + "\n"
    path.write_text(text, encoding="utf-8")
