"""Rules-based financial event classifier with precedence resolution and trigger explainability."""

import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.common.config import load_engine_config
from src.common.schema import EventType

logger = logging.getLogger("event_classifier")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


TEMPLATE_SPAM_PATTERN = re.compile(
    r"(?:#stickynote\b|Good\s+morning\s+TRADERS|pls\s+retweet\b|giveaway\b|G\s*I\s*V\s*E\s*A\s*W\s*A\s*Y)",
    re.IGNORECASE,
)

CALENDAR_TABLE_PATTERN = re.compile(
    r"(?:Upcoming\s+Earnings\s+Report\s*-\s*Week\s+of"
    r"|Q[1-4]\s+Revenue\s+Growth,\s+YoY"
    r"|This\s+week:\s*\d+%\s+of\s+the\s+(?:SPX|S&P)"
    r"|Most\s+Anticipated\s+Releases"
    r"|\bLargest:\s*\$[A-Z]+"
    r"|(?:Monday|Tuesday|Wednesday|Thursday|Friday)\s*-"
    r"|\b(?:Mon|Tues?|Wed|Thu|Thurs?|Fri)\s*:\s*\$[A-Z]+"
    r"|\bWeek\s+Ahead\b.*\b(?:earnings|reports)\b"
    r"|Week\s+Beginning\s+[A-Za-z]+\s+\d{1,2})",
    re.IGNORECASE,
)

ANALYST_ACTION_PATTERN = re.compile(
    r"\b(?:jpmorgan|goldman(?:\s+sachs)?|barclays|morgan\s+stanley|citi(?:group)?|bofa|bank\s+of\s+america|"
    r"jefferies|ubs|wells\s+fargo|bernstein|cowen|oppenheimer|mizuho|piper\s+sandler|canaccord|evercore|stifel|"
    r"analyst[s]?|brokerage[s]?)\b.*\b(?:upgrade[ds]?|downgrade[ds]?|reiterat(?:es?|ed)|initiates?\s+coverage|"
    r"price\s+target|target\s+price|slashes?\s+pt|raises?\s+pt|cuts?\s+pt|boosts?\s+pt)\b"
    r"|\b(?:price\s+target|target\s+price|slashes?\s+pt|raises?\s+pt|cuts?\s+pt|boosts?\s+pt)\b"
    r"|\b(?:upgraded?|downgraded?)\s+to\s+(?:buy|neutral|overweight|underweight|sell|outperform|underperform|hold)\b",
    re.IGNORECASE,
)

CREDIT_AGENCY_PATTERN = re.compile(
    r"\b(?:moody'?s|fitch|s&p|standard\s+&\s+poor'?s|credit\s+rating|junk\s+status|chapter\s+11|insolvency)\b",
    re.IGNORECASE,
)

CREDIT_SPECULATION_PATTERN = re.compile(
    r"(?:would\s+think\s+.*(?:is\s+)?going\s+bankrupt"
    r"|going\s+bankrupt\b"
    r"|going\s+to\s+go\s+bankrupt\b"
    r"|heading\s+towards\s+bankruptcy\b"
    r"|will\s+be\s+the\s+largest\s+bankruptcy\b"
    r"|was\s+heading\s+towards\s+bankruptcy\b"
    r"|was\s+going\s+bankrupt\b"
    r"|think\s+.*(?:will\s+be|is)\s+.*bankruptcy\b"
    r"|America\s+is\s+.*going\s+to\s+go\s+bankrupt\b)",
    re.IGNORECASE,
)

CREDIT_DEFAULT_SWAP_PATTERN = re.compile(
    r"\bcredit\s+default\s+swap[s]?\b",
    re.IGNORECASE,
)
CREDIT_DEFAULT_SWAP_VALID_CONTEXT = re.compile(
    r"\b(?:spread[s]?\s+widen(?:ed|ing)?|basis\s+points?|blowout|rating|downgrade)\b",
    re.IGNORECASE,
)

GEOPOLITICAL_EVENT_WORD = re.compile(
    r"\b(?:sanction[s]?|embargo[es]?|invasion|missile\s+strike[s]?|war\s+declared|tariff\s+announcement|tariffs?|export\s+controls?)\b",
    re.IGNORECASE,
)

GOVT_COUNTRY_ACTOR = re.compile(
    r"\b(?:russia|russian|china|chinese|iran|iranian|ukraine|ukrainian|u\.?s\.?|united\s+states|biden|trump|"
    r"white\s+house|pentagon|kremlin|beijing|foreign\s+ministry|central\s+bank|department\s+of\s+defense|dod)\b",
    re.IGNORECASE,
)

STOCK_OPINION_PATTERN = re.compile(
    r"\b(?:futures\s+just\s+turned|competitive\s+advantage|stock\s+opinion|call\s+options?|put\s+options?|brewing\s+again|pre-mkt|premarket)\b",
    re.IGNORECASE,
)

NATIONAL_SECURITY_SYSTEMS_PATTERN = re.compile(
    r"\bnational\s+security\s+systems?\b",
    re.IGNORECASE,
)

HYPOTHETICAL_PATTERN = re.compile(
    r"\b(?:pretty\s+sure|next\s+step\s+is|would\s+be|might\s+be|i\s+think|cramer\s+top\s+pick|joke|rumor)\b",
    re.IGNORECASE,
)


class EventClassifier:
    """Classifies unstructured financial text into 8 canonical EventType categories using weighted rules."""

    def __init__(self, config_path: str = "config/engine.yaml"):
        self.config = load_engine_config(config_path)
        cls_cfg = self.config.get("event_classification", {})

        self.precedence = cls_cfg.get("precedence", [
            "Credit Event",
            "Geopolitical",
            "Merger/Acquisition",
            "Regulatory",
            "Earnings",
            "Product Launch",
            "Macroeconomic",
            "Other",
        ])
        # Map precedence category to index (lower is higher priority)
        self.precedence_rank = {cat: i for i, cat in enumerate(self.precedence)}

        # Compile triggers: {category: [(compiled_regex, weight, raw_pattern)]}
        self.compiled_triggers: Dict[str, List[Tuple[re.Pattern, float, str]]] = {}
        triggers_cfg = cls_cfg.get("triggers", {})

        for cat, trigger_list in triggers_cfg.items():
            compiled_list = []
            for t in trigger_list:
                pat_str = t["pattern"]
                w = float(t.get("weight", 0.9))
                try:
                    comp_pat = re.compile(pat_str, re.IGNORECASE)
                    compiled_list.append((comp_pat, w, pat_str))
                except re.error as e:
                    logger.warning(f"Failed to compile pattern '{pat_str}' for {cat}: {e}")
            self.compiled_triggers[cat] = compiled_list

    def classify(
        self,
        text: str,
        source: Optional[str] = None,
        macro_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Classify a single text string into EventType with confidence, triggers, and secondary event."""
        if not isinstance(text, str) or not text.strip():
            return {
                "event_type": EventType.OTHER.value,
                "confidence": 0.0,
                "matched_triggers": [],
                "secondary_event": None,
                "is_template": False,
                "is_analyst_action": False,
            }

        cleaned_text = text.strip()
        is_templ = bool(TEMPLATE_SPAM_PATTERN.search(cleaned_text))
        cashtags = re.findall(r"\$[A-Za-z]+", cleaned_text)
        is_cal = bool(CALENDAR_TABLE_PATTERN.search(cleaned_text) or len(cashtags) >= 5)

        category_matches: Dict[str, List[Tuple[str, float]]] = {}

        # 1. Evaluate regex triggers across each category
        for cat, trigger_list in self.compiled_triggers.items():
            matched_for_cat: List[Tuple[str, float]] = []
            for comp_pat, weight, raw_pat in trigger_list:
                m = comp_pat.search(cleaned_text)
                if m:
                    matched_text = m.group(0)
                    matched_for_cat.append((matched_text, weight))
            if matched_for_cat:
                category_matches[cat] = matched_for_cat

        # Special Tightening 1: Credit Event Exclusions (must be company's own financial distress)
        credit_cat = EventType.CREDIT_EVENT.value
        if credit_cat in category_matches:
            is_speculative = bool(CREDIT_SPECULATION_PATTERN.search(cleaned_text))
            has_bare_cds = bool(CREDIT_DEFAULT_SWAP_PATTERN.search(cleaned_text)) and not bool(CREDIT_DEFAULT_SWAP_VALID_CONTEXT.search(cleaned_text))
            has_real_rating = bool(CREDIT_AGENCY_PATTERN.search(cleaned_text))
            has_filing_verb = bool(re.search(
                r"\b(?:fil(?:es?|ed|ing)\s+for\s+bankruptcy|fil(?:es?|ed|ing)\s+for\s+chapter\s+11|chapter\s+11|chapter\s+7|defaults?\s+on|defaulted\s+on|debt\s+restructuring|(?:missed|fails?\s+to\s+pay)\b.*?payment|insolvency)\b",
                cleaned_text,
                re.IGNORECASE,
            ))
            if is_speculative or has_bare_cds or (not has_real_rating and not has_filing_verb):
                del category_matches[credit_cat]

        # Special Tightening 2: Geopolitical Exclusions
        geo_cat = EventType.GEOPOLITICAL.value
        if geo_cat in category_matches:
            if NATIONAL_SECURITY_SYSTEMS_PATTERN.search(cleaned_text):
                del category_matches[geo_cat]

        # 2. Integrate existing macro_tags feature from entity linking
        if macro_tags:
            valid_tags = [t for t in macro_tags if t and isinstance(t, str)]
            if valid_tags:
                macro_cat = EventType.MACROECONOMIC.value
                if macro_cat not in category_matches:
                    category_matches[macro_cat] = []
                for tag in valid_tags:
                    category_matches[macro_cat].append((f"macro_tag:{tag}", 0.90))

        # 3. Determine winner and runner-up
        if not category_matches:
            # Unmatched chatter / noisy tweets default to Other with low confidence
            return {
                "event_type": EventType.OTHER.value,
                "confidence": 0.20,
                "matched_triggers": [],
                "secondary_event": None,
                "is_template": is_templ or is_cal,
                "is_calendar": is_cal,
                "is_analyst_action": False,
            }

        # Compute aggregate score for each matched category:
        # max single trigger weight + 0.05 bonus for multiple distinct trigger hits (capped at 1.0)
        candidate_scores: List[Tuple[str, float, int, List[str]]] = []
        for cat, matches in category_matches.items():
            max_w = max(w for _, w in matches)
            bonus = min(0.10, 0.05 * (len(matches) - 1)) if len(matches) > 1 else 0.0
            total_score = min(1.0, max_w + bonus)
            prec_rank = self.precedence_rank.get(cat, 99)
            trigger_terms = sorted(list({m[0] for m in matches}))
            candidate_scores.append((cat, total_score, prec_rank, trigger_terms))

        # Sort candidates: primary sort by total_score desc, secondary sort by precedence rank asc
        candidate_scores.sort(key=lambda x: (-x[1], x[2]))

        primary_cat, primary_score, _, primary_triggers = candidate_scores[0]
        secondary_event = candidate_scores[1][0] if len(candidate_scores) > 1 else None

        # Check analyst action
        is_analyst = False
        if primary_cat == EventType.EARNINGS.value and ANALYST_ACTION_PATTERN.search(cleaned_text):
            is_analyst = True
            if "analyst_action" not in primary_triggers:
                primary_triggers.append("analyst_action")

        src = (source or "").lower()
        # Geopolitical tweet validation
        if primary_cat == EventType.GEOPOLITICAL.value and src in ["twitter", "twitter_kaggle"]:
            has_real_event = bool(GEOPOLITICAL_EVENT_WORD.search(cleaned_text))
            has_actor = bool(GOVT_COUNTRY_ACTOR.search(cleaned_text))
            is_stock_opinion = bool(STOCK_OPINION_PATTERN.search(cleaned_text))
            if not has_real_event or (is_stock_opinion and not has_actor):
                primary_cat = EventType.OTHER.value
                primary_score = 0.20
                primary_triggers = []
            elif not has_actor:
                primary_score = min(primary_score, 0.60)

        # Check hypothetical/joking tweet cap
        if src in ["twitter", "twitter_kaggle"]:
            if HYPOTHETICAL_PATTERN.search(cleaned_text) and not CREDIT_AGENCY_PATTERN.search(cleaned_text):
                primary_score = min(primary_score, 0.60)

        return {
            "event_type": primary_cat,
            "confidence": round(float(primary_score), 4),
            "matched_triggers": primary_triggers,
            "secondary_event": secondary_event,
            "is_template": is_templ or is_cal,
            "is_calendar": is_cal,
            "is_analyst_action": is_analyst,
        }

    def classify_dataframe(
        self,
        df: pd.DataFrame,
        text_col: str = "text",
        macro_tags_col: Optional[str] = "macro_tags",
        source_col: Optional[str] = "source",
    ) -> pd.DataFrame:
        """Classify events across a dataframe and append classification columns."""
        texts = df[text_col].fillna("").astype(str).tolist()
        sources = df[source_col].tolist() if source_col and source_col in df.columns else [None] * len(df)

        if macro_tags_col and macro_tags_col in df.columns:
            macro_tags_series = df[macro_tags_col].tolist()
        else:
            macro_tags_series = [None] * len(df)

        event_types = []
        event_confidences = []
        matched_triggers_list = []
        secondary_events = []
        is_template_list = []
        is_calendar_list = []
        is_analyst_action_list = []

        for t, s, tags in zip(texts, sources, macro_tags_series):
            res = self.classify(t, source=s, macro_tags=tags)
            event_types.append(res["event_type"])
            event_confidences.append(res["confidence"])
            matched_triggers_list.append(res["matched_triggers"])
            secondary_events.append(res["secondary_event"])
            is_template_list.append(res["is_template"])
            is_calendar_list.append(res.get("is_calendar", False))
            is_analyst_action_list.append(res["is_analyst_action"])

        df_out = df.copy()
        df_out["event_type"] = event_types
        df_out["event_confidence"] = event_confidences
        df_out["matched_triggers"] = matched_triggers_list
        df_out["secondary_event"] = secondary_events
        df_out["is_template"] = is_template_list
        df_out["is_calendar"] = is_calendar_list
        df_out["is_analyst_action"] = is_analyst_action_list
        return df_out

