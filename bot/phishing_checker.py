"""Erkennt potenzielle Phishing-Links in Nachrichten (ohne discord-Importe)."""

from __future__ import annotations

import re
import urllib.parse
from typing import List, Optional, Set, Tuple

URL_RE = re.compile(r"https?://[^\s<>()\"']+|www\.[^\s<>()\"']+", re.IGNORECASE)

SUSPICIOUS_TLDS = {
    "gq", "tk", "ml", "ga", "cf", "xyz", "top", "club", "icu", "online",
    "site", "buzz", "click", "link", "ru", "cn", "zip", "work", "crypto",
    "support", "quest", "faith", "loan", "mom", "lol", "vip", "ws", "cc",
    "su", "pw",
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "buff.ly", "rb.gy",
    "cutt.ly", "tiny.cc", "shorturl.at", "ow.ly", "rebrand.ly",
}

STRONG_PATH = (
    "verify", "login", "signin", "claim", "giveaway", "nitro", "steam",
    "prize", "reward", "free", "gift",
)

STRONG_WORDS = (
    "free nitro", "nitro gift", "discord nitro", "steam gift", "steam key",
    "giveaway", "claim your", "verify your account", "account will be",
    "urgent", "expires", "paypal", "crypto", "wallet",
)

IPV4_RE = re.compile(r"\d{1,3}(\.\d{1,3}){3}")


class PhishingResult:
    def __init__(self, domain: str, reason: str) -> None:
        self.domain = domain
        self.reason = reason


def _normalize(raw: str) -> Tuple[str, str]:
    url = raw
    if raw.lower().startswith("www."):
        url = "https://" + raw
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return "", url
    host = (parsed.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host, url


def _matches(host: str, entries: Set[str]) -> bool:
    return any(host == e or host.endswith("." + e) for e in entries)


def _score(host: str, url: str, text: str) -> Tuple[List[str], List[str]]:
    strong: List[str] = []
    weak: List[str] = []

    if IPV4_RE.fullmatch(host):
        strong.append("IP-Adresse als Link")

    labels = host.split(".")
    tld = labels[-1] if len(labels) >= 2 else host
    if tld in SUSPICIOUS_TLDS:
        weak.append(f"Verdächtige TLD .{tld}")

    tail = ".".join(labels[-2:])
    if host in SHORTENERS or tail in SHORTENERS:
        weak.append("URL-Verkürzer")

    if any(k in url.lower() for k in STRONG_PATH):
        strong.append("Verdächtiger Pfad")

    if any(w in text.lower() for w in STRONG_WORDS):
        strong.append("Verdächtiger Text")

    return strong, weak


def check(
    text: str, blocklist: Set[str], allowlist: Set[str]
) -> Optional[PhishingResult]:
    if not text:
        return None
    matches = URL_RE.findall(text)
    if not matches:
        return None

    for raw in matches:
        host, url = _normalize(raw)
        if not host:
            continue

        if _matches(host, allowlist):
            continue

        for entry in blocklist:
            if host == entry or host.endswith("." + entry):
                return PhishingResult(host, f"Blacklist: {entry}")

        strong, weak = _score(host, url, text)
        if strong:
            return PhishingResult(host, strong[0])
        if len(weak) >= 2:
            return PhishingResult(host, f"{weak[0]} (kombinierte Signale)")

    return None