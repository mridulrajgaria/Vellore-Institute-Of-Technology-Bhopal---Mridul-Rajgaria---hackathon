"""Entity linking, cashtag parsing, and contextual disambiguation pipeline.

CONFIDENCE TABLE BY MATCH TYPE:
- cashtag: 0.95 (Explicit verified $TICKER cashtags in known universe)
- company_name: 0.85 (Direct or disambiguated company name/alias match)
- product_or_exec: 0.75 (Flagship product, service, or prominent executive match)
- ticker_symbol: 0.60 (Unambiguous bare uppercase ticker symbol)
- hint_only: 0.40 (Scrape hint when text has zero real entity evidence)
"""

from collections import Counter
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.common.config import load_companies_config, load_default_config

logger = logging.getLogger("entity_linking")

CONFIDENCE_TABLE: Dict[str, float] = {
    "cashtag": 0.95,
    "company_name": 0.85,
    "product_or_exec": 0.75,
    "ticker_symbol": 0.60,
    "hint_only": 0.40,
}

# Tickers that must NEVER be matched as bare words (must use $CASHTAG or full company name)
AMBIGUOUS_TICKER_SYMBOLS: Set[str] = {"PG", "KO", "BA", "COST", "AMD", "META", "GS", "DIS"}

# Currency codes and magnitude suffixes to reject from cashtags
CURRENCY_CODES: Set[str] = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR"}

# Cashtag regex: starts with $, 1-5 letters, optional class suffix of . and 1-2 letters (e.g. BRK.B)
# Handles glued text like ETF$VOO, followed by non-alpha boundary
CASHTAG_PATTERN = re.compile(r"\$([A-Za-z]{1,5}(?:\.[A-Za-z]{1,2})?)\b(?![0-9A-Za-z])")

# Macroeconomic keywords indicating MARKET category
MACRO_KEYWORDS = [
    r"\bfederal reserve\b",
    r"\bfed\b",
    r"\bfomc\b",
    r"\binterest rates?\b",
    r"\brate hikes?\b",
    r"\brate cuts?\b",
    r"\binflation\b",
    r"\bcpi\b",
    r"\btreasury yields?\b",
    r"\bs&p 500\b",
    r"\bs&p\b",
    r"\bwall street\b",
    r"\bcentral bank\b",
    r"\bmonetary policy\b",
]
MACRO_REGEX = re.compile("|".join(MACRO_KEYWORDS), re.IGNORECASE)


class EntityLinker:
    """Contextual entity linker mapping unstructured text to ticker symbols."""

    def __init__(self, companies_yaml_path: str = "config/companies.yaml"):
        self.companies_cfg = load_companies_config(companies_yaml_path).get("companies", {})

        # Ticker aliases mapping
        self.alias_to_canonical: Dict[str, str] = {
            "GOOG": "GOOGL",
            "FB": "META",
            "SPY": "MARKET",
        }

        # Valid universe set
        self.valid_tickers: Set[str] = set()
        for t in self.companies_cfg.keys():
            canonical = self.alias_to_canonical.get(t, t)
            self.valid_tickers.add(canonical)
            self.valid_tickers.add(t)

        # Precompile matchers per company
        self.company_matchers: Dict[str, Dict[str, Any]] = {}
        for ticker, data in self.companies_cfg.items():
            canonical = self.alias_to_canonical.get(ticker, ticker)
            aliases = data.get("aliases", [])
            products = data.get("products", [])
            executives = data.get("executives", [])
            context_words = data.get("context_words", [])
            is_ambiguous = data.get("is_ambiguous", False)

            alias_patterns = [rf"\b{re.escape(a)}\b" for a in aliases]
            product_patterns = [rf"\b{re.escape(p)}\b" for p in products]
            exec_patterns = [rf"\b{re.escape(e)}\b" for e in executives]
            context_patterns = [rf"\b{re.escape(c)}\b" for c in context_words]

            self.company_matchers[ticker] = {
                "canonical": canonical,
                "is_ambiguous": is_ambiguous,
                "alias_re": re.compile("|".join(alias_patterns), re.IGNORECASE) if alias_patterns else None,
                "product_exec_re": re.compile("|".join(product_patterns + exec_patterns), re.IGNORECASE) if (product_patterns or exec_patterns) else None,
                "context_re": re.compile("|".join(context_patterns), re.IGNORECASE) if context_patterns else None,
                "aliases": aliases,
                "products": products,
                "executives": executives,
            }

    def canonicalize_ticker(self, ticker: str) -> str:
        """Map aliases like GOOG -> GOOGL, FB -> META, and SPY -> MARKET."""
        t_upper = ticker.upper()
        return self.alias_to_canonical.get(t_upper, t_upper)

    def extract_cashtags(self, text: str) -> Tuple[List[str], List[str]]:
        """Extract cashtags from text, separating into valid universe cashtags and other_cashtags."""
        raw_matches = CASHTAG_PATTERN.findall(text)
        valid_cashtags: List[str] = []
        other_cashtags: List[str] = []

        for match in raw_matches:
            tag_upper = match.upper()
            if tag_upper in CURRENCY_CODES:
                continue

            canonical = self.canonicalize_ticker(tag_upper)
            if canonical in self.valid_tickers or tag_upper in self.valid_tickers:
                valid_cashtags.append(canonical)
            else:
                other_cashtags.append(tag_upper)

        return valid_cashtags, other_cashtags

    def link(
        self,
        text: str,
        ticker_hint: Optional[str] = None,
        source: Optional[str] = None,
        ticker_hints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Perform contextual entity linking and return structured results dictionary."""
        if not isinstance(text, str):
            text = ""

        # Determine candidate hints
        if ticker_hints:
            all_hints = [self.canonicalize_ticker(h) for h in ticker_hints if h]
        elif ticker_hint:
            all_hints = [self.canonicalize_ticker(ticker_hint)]
        else:
            all_hints = []

        # 1. Cashtag Extraction
        valid_cashtags, other_cashtags = self.extract_cashtags(text)
        cashtag_counts = Counter(valid_cashtags)

        # Track first position of each match in text for deterministic tie-breaking
        earliest_pos: Dict[str, int] = {}
        mention_counts: Dict[str, int] = Counter()

        # Record cashtag matches
        matches: Dict[str, Tuple[str, float, str]] = {}  # ticker -> (match_type, confidence, term)

        for tag, count in cashtag_counts.items():
            matches[tag] = ("cashtag", CONFIDENCE_TABLE["cashtag"], f"${tag}")
            pos = text.upper().find(f"${tag}")
            earliest_pos[tag] = pos if pos != -1 else 0
            mention_counts[tag] += count

        # 2. Company Name, Aliases, Products, Executives & Bare Tickers
        for ticker, match_info in self.company_matchers.items():
            canonical = match_info["canonical"]
            if canonical == "MARKET":
                continue

            # Product or Executive Match (0.75)
            prod_exec_re = match_info["product_exec_re"]
            if prod_exec_re:
                m = prod_exec_re.search(text)
                if m:
                    matched_term = m.group(0)
                    if canonical not in matches or matches[canonical][1] < CONFIDENCE_TABLE["product_or_exec"]:
                        matches[canonical] = ("product_or_exec", CONFIDENCE_TABLE["product_or_exec"], matched_term)
                    earliest_pos[canonical] = min(earliest_pos.get(canonical, m.start()), m.start())
                    mention_counts[canonical] += 1

            # Company Name / Alias Match (0.85)
            alias_re = match_info["alias_re"]
            if alias_re:
                m = alias_re.search(text)
                if m:
                    matched_alias = m.group(0)
                    is_ambiguous = match_info["is_ambiguous"]

                    if is_ambiguous:
                        context_re = match_info["context_re"]
                        has_context = bool(context_re and context_re.search(text))
                        has_cashtag = canonical in matches
                        is_multiword = len(matched_alias.split()) > 1 or "." in matched_alias

                        if has_context or has_cashtag or is_multiword:
                            if canonical not in matches or matches[canonical][1] < CONFIDENCE_TABLE["company_name"]:
                                matches[canonical] = ("company_name", CONFIDENCE_TABLE["company_name"], matched_alias)
                            earliest_pos[canonical] = min(earliest_pos.get(canonical, m.start()), m.start())
                            mention_counts[canonical] += 1
                    else:
                        if canonical not in matches or matches[canonical][1] < CONFIDENCE_TABLE["company_name"]:
                            matches[canonical] = ("company_name", CONFIDENCE_TABLE["company_name"], matched_alias)
                        earliest_pos[canonical] = min(earliest_pos.get(canonical, m.start()), m.start())
                        mention_counts[canonical] += 1

            # Bare Ticker Symbol (0.60) - Never for ambiguous tickers
            if ticker not in AMBIGUOUS_TICKER_SYMBOLS and canonical not in AMBIGUOUS_TICKER_SYMBOLS:
                bare_re = re.compile(rf"\b{re.escape(ticker)}\b")
                m = bare_re.search(text)
                if m:
                    if canonical not in matches or matches[canonical][1] < CONFIDENCE_TABLE["ticker_symbol"]:
                        matches[canonical] = ("ticker_symbol", CONFIDENCE_TABLE["ticker_symbol"], ticker)
                    earliest_pos[canonical] = min(earliest_pos.get(canonical, m.start()), m.start())
                    mention_counts[canonical] += 1

        # 3. Macro / Market Detection
        macro_match = MACRO_REGEX.search(text)
        has_market_tag = False
        if macro_match:
            has_market_tag = True
            matched_macro = macro_match.group(0)
            if "MARKET" not in matches:
                matches["MARKET"] = ("company_name", CONFIDENCE_TABLE["company_name"], matched_macro)
            earliest_pos["MARKET"] = min(earliest_pos.get("MARKET", macro_match.start()), macro_match.start())

        # Separate company tickers from MARKET
        company_tickers = [t for t in matches.keys() if t != "MARKET"]
        n_linked_tickers = len(company_tickers)

        # 4. Fallback / Hint Isolation Rule
        # If ZERO real evidence in text:
        if not matches:
            if source in ["twitter", "twitter_kaggle"] and all_hints:
                c_hint = sorted(all_hints)[0]
                return {
                    "linked_tickers": [c_hint],
                    "primary_ticker": c_hint,
                    "link_type": "hint_only",
                    "link_confidence": CONFIDENCE_TABLE["hint_only"],
                    "n_linked_tickers": 1,
                    "is_broadcast": False,
                    "other_cashtags": other_cashtags,
                    "attribution_weight": 1.0,
                    "is_relevant": True,
                    "matched_term": "hint",
                    "resolved_hint": c_hint,
                }
            else:
                return {
                    "linked_tickers": [],
                    "primary_ticker": None,
                    "link_type": None,
                    "link_confidence": None,
                    "n_linked_tickers": 0,
                    "is_broadcast": False,
                    "other_cashtags": other_cashtags,
                    "attribution_weight": 0.0,
                    "is_relevant": False,
                    "matched_term": None,
                    "resolved_hint": sorted(all_hints)[0] if all_hints else ticker_hint,
                }

        # 5. Determine Primary Ticker & Broadcast Status
        is_broadcast = n_linked_tickers >= 3
        primary_ticker: Optional[str] = None
        top_type: Optional[str] = None
        top_conf: Optional[float] = None
        top_term: Optional[str] = None

        # Resolve which hint is in linked_tickers (matches)
        matching_hints = [h for h in all_hints if h in matches]
        resolved_hint = sorted(matching_hints)[0] if matching_hints else (sorted(all_hints)[0] if all_hints else ticker_hint)

        if is_broadcast:
            # Rule 1: For n_linked_tickers >= 3, primary_ticker = None (NOT hint, NOT earliest)
            primary_ticker = None
            top_type = "cashtag" if any(matches[t][0] == "cashtag" for t in company_tickers) else "company_name"
            top_conf = max(matches[t][1] for t in company_tickers)
            top_term = "broadcast"
        elif n_linked_tickers == 1:
            # Rule 2: Exactly 1 real company ticker wins, even if differs from hint
            primary_ticker = company_tickers[0]
            top_type, top_conf, top_term = matches[primary_ticker]
        elif n_linked_tickers == 2:
            # Rule 3: Exactly 2 real company tickers
            hints_in_comp = [h for h in all_hints if h in company_tickers]
            if hints_in_comp:
                primary_ticker = sorted(hints_in_comp)[0]
            else:
                # One mentioned most; ties go to earliest
                t1, t2 = company_tickers[0], company_tickers[1]
                count1, count2 = mention_counts[t1], mention_counts[t2]
                if count1 > count2:
                    primary_ticker = t1
                elif count2 > count1:
                    primary_ticker = t2
                else:
                    primary_ticker = t1 if earliest_pos.get(t1, 0) <= earliest_pos.get(t2, 0) else t2
            top_type, top_conf, top_term = matches[primary_ticker]
        elif n_linked_tickers == 0:
            # Only MARKET / SPY matched
            if "MARKET" in matches:
                primary_ticker = "MARKET"
                top_type, top_conf, top_term = matches["MARKET"]

        # Attribution weight: 1.0 / n_linked_tickers for company tickers, 1.0 for MARKET-only, 1.0 for hint_only
        if n_linked_tickers > 0:
            attribution_weight = round(1.0 / n_linked_tickers, 4)
        else:
            attribution_weight = 1.0

        # Ordered linked_tickers: primary first (if set), then others alphabetically
        all_linked = sorted(list(matches.keys()))
        if primary_ticker and primary_ticker in all_linked:
            all_linked.remove(primary_ticker)
            all_linked.insert(0, primary_ticker)

        # Relevance determination
        if source in ["newsapi", "gdelt"]:
            # Relevant only if real match occurred
            is_relevant = len(matches) > 0 and any(m[0] != "hint_only" for m in matches.values())
        else:
            is_relevant = True

        return {
            "linked_tickers": all_linked,
            "primary_ticker": primary_ticker,
            "link_type": top_type,
            "link_confidence": top_conf,
            "n_linked_tickers": n_linked_tickers,
            "is_broadcast": is_broadcast,
            "other_cashtags": sorted(list(set(other_cashtags))),
            "attribution_weight": attribution_weight,
            "is_relevant": is_relevant,
            "matched_term": top_term,
            "resolved_hint": resolved_hint,
        }


def enrich_dataframe(df: pd.DataFrame, linker: Optional[EntityLinker] = None) -> pd.DataFrame:
    """Enrich dataframe with linked_tickers, n_linked_tickers, is_broadcast, other_cashtags, attribution_weight."""
    if linker is None:
        linker = EntityLinker()

    linked_tickers_col: List[List[str]] = []
    primary_ticker_col: List[Optional[str]] = []
    link_type_col: List[Optional[str]] = []
    link_conf_col: List[Optional[float]] = []
    n_linked_col: List[int] = []
    is_broadcast_col: List[bool] = []
    other_cashtags_col: List[List[str]] = []
    attr_weight_col: List[float] = []
    is_relevant_col: List[bool] = []
    matched_term_col: List[Optional[str]] = []
    ticker_hint_col: List[Optional[str]] = []

    has_hints = "ticker_hints" in df.columns

    for idx, (text, ticker_hint, source) in enumerate(zip(
        df["text"],
        df.get("ticker_hint", [None] * len(df)),
        df.get("source", ["unknown"] * len(df)),
    )):
        row_hints = df["ticker_hints"].iloc[idx] if has_hints else None
        res = linker.link(str(text), ticker_hint=ticker_hint, source=source, ticker_hints=row_hints)

        linked_tickers_col.append(res["linked_tickers"])
        primary_ticker_col.append(res["primary_ticker"])
        link_type_col.append(res["link_type"])
        link_conf_col.append(res["link_confidence"])
        n_linked_col.append(res["n_linked_tickers"])
        is_broadcast_col.append(res["is_broadcast"])
        other_cashtags_col.append(res["other_cashtags"])
        attr_weight_col.append(res["attribution_weight"])
        is_relevant_col.append(res["is_relevant"])
        matched_term_col.append(res["matched_term"])
        ticker_hint_col.append(res.get("resolved_hint", ticker_hint))

    enriched = df.copy()
    if has_hints:
        enriched["ticker_hint"] = ticker_hint_col
    enriched["linked_tickers"] = linked_tickers_col
    enriched["primary_ticker"] = primary_ticker_col
    enriched["link_type"] = link_type_col
    enriched["link_confidence"] = link_conf_col
    enriched["n_linked_tickers"] = n_linked_col
    enriched["is_broadcast"] = is_broadcast_col
    enriched["other_cashtags"] = other_cashtags_col
    enriched["attribution_weight"] = attr_weight_col
    enriched["is_relevant"] = is_relevant_col
    enriched["matched_term"] = matched_term_col
    return enriched
