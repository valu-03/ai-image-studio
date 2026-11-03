"""The Look the page is showing: a card state plus which cards the user touched.

Thread-safe: the page, the job threads and the Local API all read it.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import look_cards  # noqa: E402


class LookState:
    def __init__(self, kind="animal", seed=0):
        self._lock = threading.RLock()
        self.kind = kind
        self.cards = look_cards.defaults(kind, seed)
        self.touched = set()
        self.extra = []
        self.overrides = {}

    def reset(self, kind, seed, avoid=(), weights=None):
        """New kind (or a fresh roll): defaults back, nothing touched."""
        with self._lock:
            self.kind = kind
            self.cards = look_cards.defaults(kind, seed, avoid=avoid, weights=weights)
            self.touched = set()
            self.extra = []

    def set_override(self, part, phrase):
        """Set or clear a phrase built in one of the Look sub-builders."""
        with self._lock:
            cleaned = str(phrase or "").strip()
            if cleaned:
                self.overrides[part] = cleaned
            else:
                self.overrides.pop(part, None)

    def set_card(self, card, option, deliberate=True):
        """Choose an option. ValueError if the card or option does not exist for
        this kind. `deliberate` marks the card as the user's own choice."""
        with self._lock:
            by_id = {c["id"]: {o["key"] for o in c["options"]}
                     for c in look_cards.cards(self.kind)}
            if card not in by_id:
                raise ValueError("unknown card: {}".format(card))
            if option not in by_id[card]:
                raise ValueError("{}: unknown option '{}'".format(card, option))
            self.cards[card] = option
            if deliberate:
                self.touched.add(card)

    def add_extra(self, phrase):
        with self._lock:
            if phrase and phrase not in self.extra:
                self.extra.append(phrase)

    def snapshot(self):
        with self._lock:
            return {"kind": self.kind, "cards": dict(self.cards),
                    "touched": sorted(self.touched), "extra": list(self.extra),
                    "overrides": dict(self.overrides)}

    def current_phrases(self):
        """Only the touched cards and applied Look sub-builder overrides, as Local API LOOK_KEY phrases."""
        with self._lock:
            chosen = {c: o for c, o in self.cards.items() if c in self.touched}
            out = look_cards.phrases(chosen, self.kind) if chosen else {}
            out.update(self.overrides)
            return out
