"""Text preprocessing utilities for sentiment and NLP models."""

import re
from typing import Optional

FINANCE_VERBS_OR_CONTENT = re.compile(
    r"\b(is|are|was|were|has|have|had|will|would|can|could|may|might|should|"
    r"surge|surges|surged|jump|jumps|jumped|drop|drops|dropped|fall|falls|fell|"
    r"rise|rises|rose|gain|gains|gained|plunge|plunges|plunged|sink|sinks|sank|"
    r"slump|slumps|slumped|climb|climbs|climbed|tumble|tumbles|tumbled|rally|rallies|"
    r"beat|beats|miss|misses|report|reports|reported|post|posts|posted|lead|leads|"
    r"hit|hits|see|sees|saw|hike|hikes|cut|cuts|cost|costs|trade|war|warn|warns|"
    r"boost|boosts|slide|slides|slid|profit|revenue|losses|earnings|inflation)\b",
    re.IGNORECASE,
)

CASHTAG_REGEX = re.compile(r"\$([A-Za-z]{1,5}(?:\.[A-Za-z]{1,2})?)\b(?![0-9A-Za-z])")


def strip_publisher_suffix(text: str) -> str:
    """Strip trailing publisher suffixes after ' - ', ' – ', ' — ', or ' | ' when suffix is a site name.

    Only strips if the suffix is short (fewer than 8 words) and contains no verb-like finance content.
    """
    pattern = re.compile(r"\s+(?:–|—|-|\|)\s+([^–—\-\|]+)$")
    cleaned = text.strip()
    while True:
        match = pattern.search(cleaned)
        if not match:
            break
        suffix = match.group(1).strip()
        words = suffix.split()
        if 0 < len(words) < 8 and not FINANCE_VERBS_OR_CONTENT.search(suffix):
            if suffix[0].isupper() or "." in suffix:
                cleaned = cleaned[:match.start()].strip()
            else:
                break
        else:
            break
    return cleaned


def fix_token_spacing(text: str) -> str:
    """Fix token-spacing artifacts from news feeds (e.g., GDELT).

    Fixes:
    - Numbers with spaced commas or periods: '$17 , 500' -> '$17,500', '$32 . 5' -> '$32.5'
    - Spaced hyphens between alphanumeric words: 'bail - outs' -> 'bail-outs', 'all - out' -> 'all-out'
    - Spaces before punctuation marks: 'word . Next' -> 'word. Next', 'vs .' -> 'vs.', ' ?' -> '?'
    """
    if not isinstance(text, str):
        return ""

    # Numbers with separated commas or dots: 17 , 500 -> 17,500 ; 32 . 5 -> 32.5
    text = re.sub(r"(?<=\d)\s*,\s*(?=\d)", ",", text)
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)

    # Spaced hyphens in words (compound words where second word starts with lowercase, or digits):
    # bail - outs -> bail-outs ; all - out -> all-out
    text = re.sub(r"(?<=[a-zA-Z0-9])\s+-\s+(?=[a-z0-9])", "-", text)

    # Spaces before punctuation marks: word . Next -> word. Next ; vs . -> vs. ; ? -> ?
    text = re.sub(r"\s+([,.:;?!])(?=\s|$)", r"\1", text)

    return text


def clean_for_model(text: str, source: Optional[str] = None) -> str:
    """Prepare text for transformer model input.

    - GDELT / NewsAPI: Strip trailing publisher suffixes and fix token spacing.
    - Tweets: Retain mentions/punctuation, replace $CASHTAGS with plain symbols, and cap at 128 words.
    - All: Collapse redundant whitespace.
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    src = (source or "").lower()

    if src in ["gdelt", "newsapi"]:
        # 1. Strip publisher suffixes first (before modifying hyphens)
        text = strip_publisher_suffix(text)
        # 2. Fix token-spacing artifacts
        text = fix_token_spacing(text)
    elif src in ["twitter", "twitter_kaggle"]:
        # Replace $CASHTAG with plain symbol for model input only (e.g. $TSLA -> TSLA, ETF$VOO -> ETF VOO)
        text = CASHTAG_REGEX.sub(r" \1 ", text)
    else:
        # Generic text source (e.g., financial_phrasebank): apply spacing fix
        text = fix_token_spacing(text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Cap words at 128 tokens
    words = text.split()
    if len(words) > 128:
        text = " ".join(words[:128])

    return text
