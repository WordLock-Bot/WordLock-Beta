"""WordLock filter engine.

The engine detects bad words even when the sender tries to evade the filter.

Approach
--------
Every word in a dictionary is *normalized* into a canonical form:

    "id.iot"   -> "idiot"
    "1di0t"    -> "idiot"
    "i d i o t"-> "idiot"
    "idiot!!!" -> "idiot"
    "1d10t"    -> "idiot"
    "idi0t"    -> "idiot"

Normalization steps:
    1. lower-case
    2. Unicode NFKD + strip combining marks (é -> e, а-cyrillic homoglyph)
    3. confusable / homoglyph substitution (Cyrillic "а" -> "a")
    4. leetspeak substitution (0->o, 1->i/l, 3->e, 4->a, 5->s, 7->t, ...)
    5. remove every character that is not [a-z0-9]
    6. collapse repeated characters ("idiottt" -> "idiot", "c00l" -> "col")

Both the dictionary words and the incoming message go through the same
pipeline, then the normalized dictionary patterns are matched against the
normalized message using an Aho-Corasick automaton (fast, single pass, and
immune to whitespace / punctuation insertion between letters).

Known limitation
----------------
Vowel-insertion evasion (e.g. "f()ck" -> normalized "fick" instead of "fuck")
is intentionally out of scope: expanding it would create false positives on
legitimate words. Bracket inserts that do not contain a vowel that would form
a different word ARE caught (e.g. "a*s*s*hole" -> "asshole").
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Evasion lookup tables
# ---------------------------------------------------------------------------

LEET_MAP: Dict[str, str] = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "g",
    "7": "t",
    "8": "b",
    "9": "g",
    "2": "z",
    "@": "a",
    "$": "s",
    "+": "t",
    "#": "h",
    "|": "i",
    "(": "c",
    ")": "c",
    "[": "c",
    "]": "c",
    "{": "c",
    "}": "c",
}

# Homoglyphs / confusables that look like ASCII letters.
CONFUSABLE_MAP: Dict[str, str] = {
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x",
    "у": "y", "в": "b", "н": "h", "к": "k", "м": "m", "т": "t",
    "і": "i", "ј": "j", "ѕ": "s", "ѕ": "s",
    # Greek
    "α": "a", "β": "b", "γ": "y", "δ": "d", "ε": "e", "η": "n",
    "θ": "o", "λ": "l", "μ": "u", "ξ": "x", "π": "n", "ρ": "p",
    "σ": "s", "τ": "t", "φ": "f", "χ": "x", "ω": "w",
    # Full-width
    "ａ": "a", "ｂ": "b", "ｃ": "c", "ｄ": "d", "ｅ": "e", "ｆ": "f",
    "ｇ": "g", "ｈ": "h", "ｉ": "i", "ｊ": "j", "ｋ": "k", "ｌ": "l",
    "ｍ": "m", "ｎ": "n", "ｏ": "o", "ｐ": "p", "ｑ": "q", "ｒ": "r",
    "ｓ": "s", "ｔ": "t", "ｕ": "u", "ｖ": "v", "ｗ": "w", "ｘ": "x",
    "ｙ": "y", "ｚ": "z",
    # Misc
    "½": "a", "₪": "i", "ø": "o", "µ": "u",
}

# Characters that are common "word boundaries" thrown into words to evade
# filters. Only letter/digit survive normalization; everything else acts as a
# separator. This map is informational (see _strip_separators).
SEPARATORS = re.compile(r"[^a-z0-9]")

# Minimum pattern length for an intra-token *substring* match. Short patterns
# like "kill" are only matched against whole tokens or cross-token evasions so
# that harmless words such as "skills" are not flagged.
MIN_SUBSTRING_LEN = 4

# Whole words that must never be flagged, even if they contain a filter word
# as a substring ("grape" -> "rape", "hello" -> "hell", "success" -> "suck").
DEFAULT_EXCEPTIONS = (
    "grape", "grapes", "success", "successful", "succeed",
    "hello", "hellish", "class", "classic", "classify", "classroom",
    "skill", "skills", "skilled", "assess", "assignment",
    "damnation", "grass", "grasp", "pass", "password",
)


def normalize(text: str) -> str:
    """Reduce an arbitrary string to its canonical detection form."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # German sharp s -> ss so "scheiße" and "scheisse" share a canonical form.
    text = text.replace("ß", "ss")

    out: List[str] = []
    for idx, ch in enumerate(text):
        # "!" only stands for "i" when embedded inside a word ("k!ll");
        # trailing/leading "!" groups ("idiot!!!") are pure punctuation.
        if ch == "!":
            prev_alnum = text[idx - 1].isalnum() if idx > 0 else False
            next_alnum = text[idx + 1].isalnum() if idx + 1 < len(text) else False
            if prev_alnum and next_alnum:
                out.append("i")
                continue
            else:
                continue
        if ch in LEET_MAP:
            out.append(LEET_MAP[ch])
        elif ch in CONFUSABLE_MAP:
            out.append(CONFUSABLE_MAP[ch])
        else:
            out.append(ch)
    text = "".join(out)
    text = SEPARATORS.sub("", text)
    # Collapse repeated characters. Two or more identical letters in a row are
    # treated as one, which catches "idiottttt" while the dictionary is
    # normalized the same way.
    text = re.sub(r"(.)\1+", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# Aho-Corasick automaton (pure Python, efficient multi-pattern matching)
# ---------------------------------------------------------------------------


class AhoCorasick:
    """Single-pass multi-pattern string matcher."""

    def __init__(self, patterns: Iterable[str]):
        self._patterns = list(dict.fromkeys(patterns))  # dedupe, keep order
        self._goto: List[Dict[str, int]] = [{}]
        self._fail: List[int] = [0]
        self._output: List[List[int]] = [[]]

        for idx, pattern in enumerate(self._patterns):
            self._add(pattern, idx)
        self._build_fail()

    def _add(self, pattern: str, pattern_index: int) -> None:
        state = 0
        for ch in pattern:
            nxt = self._goto[state].get(ch)
            if nxt is None:
                self._goto.append({})
                self._fail.append(0)
                self._output.append([])
                nxt = len(self._goto) - 1
                self._goto[state][ch] = nxt
            state = nxt
        self._output[state].append(pattern_index)

    def _build_fail(self) -> None:
        from collections import deque

        queue: deque = deque()
        for ch, state in self._goto[0].items():
            self._fail[state] = 0
            queue.append(state)

        while queue:
            r = queue.popleft()
            for ch, u in self._goto[r].items():
                queue.append(u)
                v = self._fail[r]
                while ch not in self._goto[v] and v != 0:
                    v = self._fail[v]
                self._fail[u] = self._goto[v].get(ch, 0)
                self._output[u] = self._output[u] + self._output[self._fail[u]]

    def find(self, text: str) -> List[Tuple[str, int, int]]:
        """Return [(pattern, start_index, end_index)] for every match."""
        matches: List[Tuple[str, int, int]] = []
        state = 0
        for pos, ch in enumerate(text):
            while ch not in self._goto[state] and state != 0:
                state = self._fail[state]
            state = self._goto[state].get(ch, 0)
            for pidx in self._output[state]:
                pattern = self._patterns[pidx]
                matches.append((pattern, pos - len(pattern) + 1, pos + 1))
        return matches


# ---------------------------------------------------------------------------
# Word list loading
# ---------------------------------------------------------------------------


class WordEntry:
    __slots__ = (
        "word", "category", "severity", "description",
        "source", "custom", "action",
    )

    def __init__(
        self,
        word: str,
        category: str = "custom",
        severity: int = 3,
        description: str = "",
        source: str = "custom",
        custom: bool = False,
        action: Optional[str] = None,
    ):
        self.word = word
        self.category = category
        self.severity = int(severity)
        self.description = description
        self.source = source
        self.custom = custom
        # Per-word action override (used by custom words). None = server default.
        self.action = action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "source": self.source,
            "custom": self.custom,
            "action": self.action,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"WordEntry({self.word!r}, {self.category}, {self.severity})"


def load_standard_list(language: str) -> List[WordEntry]:
    """Load a shipped standard word list from ``data/default_words_<lang>.json``."""
    path = DATA_DIR / f"default_words_{language}.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    entries: List[WordEntry] = []
    for item in payload.get("words", []):
        entries.append(
            WordEntry(
                word=item["word"],
                category=item.get("category", "profanity"),
                severity=item.get("severity", 3),
                description=item.get("description", ""),
                source=f"default_{language}",
                custom=False,
            )
        )
    return entries


def load_standard_lists(languages: Iterable[str] = ("de", "en")) -> List[WordEntry]:
    entries: List[WordEntry] = []
    for lang in languages:
        entries.extend(load_standard_list(lang))
    return entries


# ---------------------------------------------------------------------------
# The compiled filter
# ---------------------------------------------------------------------------


class FilterEngine:
    """Combines standard + custom words and checks messages against them.

    Matching is token-aware and works in three tiers:

    A) *Exact token*  — ``normalize(token) == pattern``. Catches clean words
       and single-token evasions such as ``1di0t``, ``id.iot`` or ``idiot!!!``.

    B) *Cross-token*  — a pattern formed by joining consecutive tokens
       (``i d i o t``). Only spans of >= 2 tokens count.

    C) *Substring*    — a pattern appearing as a prefix/suffix of a longer
       token (``fucking`` -> ``fuck``, ``asshole`` -> ``ass``). Only patterns
       of at least :data:`MIN_SUBSTRING_LEN` characters are eligible, and
       tokens listed in :data:`DEFAULT_EXCEPTIONS` are never flagged.
    """

    def __init__(self, default_languages: Iterable[str] = ("de", "en")):
        self._default_languages = tuple(default_languages)
        self._entries: List[WordEntry] = []
        self._patterns: Dict[str, WordEntry] = {}  # normalized word -> entry
        self._automaton: Optional[AhoCorasick] = None
        self._exceptions = {normalize(w) for w in DEFAULT_EXCEPTIONS}
        self.reload()

    # -- lifecycle ----------------------------------------------------------

    def reload(self, custom_entries: Optional[Iterable[WordEntry]] = None) -> None:
        self._entries = load_standard_lists(self._default_languages)
        if custom_entries:
            self._entries.extend(custom_entries)

        self._patterns = {}
        for entry in self._entries:
            norm = normalize(entry.word)
            if not norm:
                continue
            # Longest (most specific) entry wins when two words normalize to
            # the same canonical form.
            existing = self._patterns.get(norm)
            if existing is None or len(entry.word) > len(existing.word):
                self._patterns[norm] = entry
        self._automaton = AhoCorasick(self._patterns.keys())

    def add_entries(self, entries: Iterable[WordEntry]) -> None:
        self._entries = self._entries + list(entries)
        self.reload()

    def apply_overrides(
        self, overrides: Dict[str, Dict[str, Any]]
    ) -> None:
        """Apply per-guild overrides to the standard (non-custom) entries.

        ``overrides`` maps normalized *word* -> {action, enabled}. Disabled
        entries are removed from the filter; enabled entries get their action
        override applied. Custom entries are never touched.
        """
        changed = False
        kept: List[WordEntry] = []
        for entry in self._entries:
            if entry.custom:
                kept.append(entry)
                continue
            override = overrides.get(entry.word)
            if override is not None and not override.get("enabled", True):
                changed = True
                continue
            if override is not None and override.get("action"):
                entry.action = override["action"]
                changed = True
            kept.append(entry)
        if changed:
            self._entries = kept
            self._rebuild_patterns()

    def _rebuild_patterns(self) -> None:
        self._patterns = {}
        for entry in self._entries:
            norm = normalize(entry.word)
            if not norm:
                continue
            existing = self._patterns.get(norm)
            if existing is None or len(entry.word) > len(existing.word):
                self._patterns[norm] = entry
        self._automaton = AhoCorasick(self._patterns.keys())

    @property
    def entries(self) -> List[WordEntry]:
        return list(self._entries)

    # -- matching -----------------------------------------------------------

    def _match_for(self, pattern: str) -> WordEntry:
        return self._patterns[pattern]

    def check(
        self, text: str
    ) -> Optional[Tuple[str, int, int, WordEntry]]:
        """Return the first detected (match, start, end, entry) or ``None``.

        ``start``/``end`` are indices into the *normalized* text.
        """
        results = self.check_all(text)
        return results[0] if results else None

    def check_all(self, text: str) -> List[Tuple[str, int, int, WordEntry]]:
        if not text or self._automaton is None:
            return []

        # Whitespace tokenization (punctuation stays attached to its token).
        tokens = text.split()
        norms: List[str] = [normalize(t) for t in tokens]
        seen_entries: List[int] = []
        results: List[Tuple[str, int, int, WordEntry]] = []

        def push(pattern: str, start: int, end: int) -> None:
            entry = self._match_for(pattern)
            if id(entry) in seen_entries:
                return
            seen_entries.append(id(entry))
            results.append((pattern, start, end, entry))

        # Tier A + C: per token.
        offset = 0
        for i, tok_norm in enumerate(norms):
            if not tok_norm or tok_norm in self._exceptions:
                offset += len(tok_norm)
                continue
            # Tier A: exact match.
            if tok_norm in self._patterns:
                push(tok_norm, offset, offset + len(tok_norm))
            else:
                # Tier C: prefix / suffix substring for long-enough patterns.
                for pattern, entry in self._patterns.items():
                    if len(pattern) < MIN_SUBSTRING_LEN:
                        continue
                    if tok_norm.startswith(pattern) or tok_norm.endswith(pattern):
                        push(pattern, offset, offset + len(tok_norm))
                        break
            offset += len(tok_norm)

        # Tier B: cross-token joins ("i d i o t").
        if len(norms) >= 2:
            self._cross_token_matches(norms, push)

        return results

    def _cross_token_matches(self, norms: List[str], push) -> None:
        """Find patterns spanning at least two consecutive tokens."""
        positions: List[Tuple[str, int, int]] = []  # (tok_norm, start, end)
        cursor = 0
        for n in norms:
            if not n or n in self._exceptions:
                continue
            positions.append((n, cursor, cursor + len(n)))
            cursor += len(n)

        if len(positions) < 2:
            return

        joined = "".join(n[0] for n in positions)
        if self._automaton is None:
            return

        for pattern, start, end in self._automaton.find(joined):
            # Determine which token span covers [start, end).
            inside = [p for p in positions if p[1] < end and p[2] > start]
            if len(inside) >= 2:
                push(pattern, start, end)

    # -- introspection ------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self._entries),
            "patterns": len(self._patterns),
            "default_languages": list(self._default_languages),
            "by_category": _count_by(self._entries, "category"),
        }


def _count_by(entries: List[WordEntry], attr: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for e in entries:
        key = getattr(e, attr)
        out[key] = out.get(key, 0) + 1
    return out
