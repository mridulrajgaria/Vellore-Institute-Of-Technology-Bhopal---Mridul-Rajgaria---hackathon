"""FinBERT Sentiment Scoring with Dynamic Label Mapping and Disk Caching.

IMPORTANT DESIGN NOTE:
The `sentiment_score` computed here measures the general financial tone/sentiment of the text,
NOT the stance or sentiment toward a particular ticker mentioned in the text.
For multi-ticker and broadcast texts (e.g. where `is_broadcast` is True), attribution across tickers
is handled downstream by weighting with `attribution_weight`.
"""

import hashlib
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import torch

from src.nlp.preprocess import clean_for_model

logger = logging.getLogger("sentiment")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

CACHE_DIR_DEFAULT = Path("data/cache")
CACHE_FILE_DEFAULT = CACHE_DIR_DEFAULT / "sentiment_cache.parquet"


class FinBertScorer:
    """FinBERT sentiment scorer with CPU batching, caching, and dynamic label mapping."""

    def __init__(
        self,
        model_name_or_path: str = "models_cache/finbert",
        model: Optional[Any] = None,
        tokenizer: Optional[Any] = None,
        cache_path: Optional[Union[str, Path]] = CACHE_FILE_DEFAULT,
        batch_size: int = 32,
        num_threads: int = 4,
        max_length: int = 128,
    ):
        self.batch_size = batch_size
        self.max_length = max_length
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache: Dict[str, Dict[str, Any]] = {}

        # Set torch threads
        try:
            torch.set_num_threads(num_threads)
        except Exception:
            pass

        # Load or use injected model & tokenizer
        if model is not None and tokenizer is not None:
            self.model = model
            self.tokenizer = tokenizer
        else:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            model_path = Path(model_name_or_path)
            target = str(model_path) if model_path.exists() else "ProsusAI/finbert"
            logger.info(f"Loading FinBERT model and tokenizer from {target}...")
            self.tokenizer = AutoTokenizer.from_pretrained(target)
            self.model = AutoModelForSequenceClassification.from_pretrained(target)

        self.model.eval()

        # Dynamic label mapping from model config
        # FinBERT defaults to {0: 'positive', 1: 'negative', 2: 'neutral'}
        # Never hardcode label order; dynamically map by label name (lowercase)
        id2label = getattr(self.model.config, "id2label", {0: "positive", 1: "negative", 2: "neutral"})
        self.id2label = {int(k): str(v).lower() for k, v in id2label.items()}
        self.label2id = {v: k for k, v in self.id2label.items()}

        if "positive" not in self.label2id or "negative" not in self.label2id or "neutral" not in self.label2id:
            raise ValueError(f"Model config must contain positive, negative, and neutral labels. Found: {self.id2label}")

        self.pos_idx = self.label2id["positive"]
        self.neg_idx = self.label2id["negative"]
        self.neu_idx = self.label2id["neutral"]

        # Load disk cache if enabled
        self._load_cache()

    def _load_cache(self) -> None:
        """Load sentiment cache from parquet file if exists."""
        if not self.cache_path or not self.cache_path.exists():
            return
        try:
            df_cache = pd.read_parquet(self.cache_path)
            for _, row in df_cache.iterrows():
                k = str(row["cache_key"])
                self.cache[k] = {
                    "sentiment_score": float(row["sentiment_score"]),
                    "sentiment_label": str(row["sentiment_label"]),
                    "sentiment_confidence": float(row["sentiment_confidence"]),
                    "p_pos": float(row["p_pos"]),
                    "p_neg": float(row["p_neg"]),
                    "p_neu": float(row["p_neu"]),
                }
            logger.info(f"Loaded {len(self.cache):,} cached sentiment entries from {self.cache_path}")
        except Exception as e:
            logger.warning(f"Could not load cache from {self.cache_path}: {e}")

    def _save_cache(self) -> None:
        """Persist memory cache to parquet file."""
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            records = [{"cache_key": k, **v} for k, v in self.cache.items()]
            df_cache = pd.DataFrame(records)
            df_cache.to_parquet(self.cache_path, index=False)
            logger.info(f"Persisted {len(df_cache):,} cached sentiment entries to {self.cache_path}")
        except Exception as e:
            logger.warning(f"Could not save cache to {self.cache_path}: {e}")

    @staticmethod
    def get_cache_key(cleaned_text: str) -> str:
        """Compute sha1 hash key for clean model input text."""
        return hashlib.sha1(cleaned_text.encode("utf-8")).hexdigest()

    def score_texts(
        self,
        texts: List[str],
        sources: Optional[List[str]] = None,
        show_progress: bool = True,
    ) -> List[Dict[str, Any]]:
        """Score a list of raw texts and sources.

        Returns list of dicts with keys:
          - sentiment_score: float in [-1.0, 1.0] (p_pos - p_neg)
          - sentiment_label: str ('positive', 'negative', 'neutral')
          - sentiment_confidence: float in [0.0, 1.0] (max prob)
          - p_pos, p_neg, p_neu: float in [0.0, 1.0]
        """
        n = len(texts)
        if sources is None:
            sources = ["" for _ in range(n)]

        cleaned_texts: List[str] = []
        keys: List[str] = []
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Step 1: Preprocess and cache lookup
        for idx, (t, s) in enumerate(zip(texts, sources)):
            cleaned = clean_for_model(t, s)
            cleaned_texts.append(cleaned)
            if not cleaned:
                key = ""
            else:
                key = self.get_cache_key(cleaned)
            keys.append(key)

            if cleaned and key not in self.cache:
                uncached_indices.append(idx)
                uncached_texts.append(cleaned)

        # Step 2: Batch inference on uncached items
        n_uncached = len(uncached_texts)
        if n_uncached > 0:
            logger.info(f"Scoring {n_uncached:,} uncached texts (out of {n:,} requested) using batch_size={self.batch_size}...")
            start_time = time.time()
            scored_so_far = 0

            for b_start in range(0, n_uncached, self.batch_size):
                b_end = min(b_start + self.batch_size, n_uncached)
                batch_text_subset = uncached_texts[b_start:b_end]

                inputs = self.tokenizer(
                    batch_text_subset,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    probs = torch.softmax(logits, dim=-1).cpu().numpy()

                for sub_i, text_str in enumerate(batch_text_subset):
                    p_pos = float(probs[sub_i, self.pos_idx])
                    p_neg = float(probs[sub_i, self.neg_idx])
                    p_neu = float(probs[sub_i, self.neu_idx])
                    score = float(p_pos - p_neg)
                    confidence = float(max(p_pos, p_neg, p_neu))

                    argmax_idx = int(probs[sub_i].argmax())
                    label = self.id2label.get(argmax_idx, "neutral")

                    k = self.get_cache_key(text_str)
                    self.cache[k] = {
                        "sentiment_score": score,
                        "sentiment_label": label,
                        "sentiment_confidence": confidence,
                        "p_pos": p_pos,
                        "p_neg": p_neg,
                        "p_neu": p_neu,
                    }

                scored_so_far += len(batch_text_subset)
                elapsed = time.time() - start_time
                if show_progress and (scored_so_far == n_uncached or (b_start // self.batch_size) % 10 == 0):
                    rate = scored_so_far / max(elapsed, 0.001)
                    logger.info(f"Progress: {scored_so_far:,}/{n_uncached:,} uncached rows scored ({rate:.1f} rows/sec)")

            self._save_cache()

        # Step 3: Build output records
        results: List[Dict[str, Any]] = []
        for idx, key in enumerate(keys):
            if not cleaned_texts[idx]:
                results.append({
                    "sentiment_score": 0.0,
                    "sentiment_label": "neutral",
                    "sentiment_confidence": 1.0,
                    "p_pos": 0.0,
                    "p_neg": 0.0,
                    "p_neu": 1.0,
                })
            else:
                results.append(dict(self.cache[key]))

        return results

    def score_dataframe(
        self,
        df: pd.DataFrame,
        text_col: str = "text",
        source_col: Optional[str] = "source",
        show_progress: bool = True,
    ) -> pd.DataFrame:
        """Score dataframe texts and return dataframe with sentiment columns appended."""
        texts = df[text_col].fillna("").astype(str).tolist()
        sources = df[source_col].fillna("").astype(str).tolist() if source_col and source_col in df.columns else None

        records = self.score_texts(texts, sources, show_progress=show_progress)
        df_scored = df.copy()
        df_scored["sentiment_score"] = [r["sentiment_score"] for r in records]
        df_scored["sentiment_label"] = [r["sentiment_label"] for r in records]
        df_scored["sentiment_confidence"] = [r["sentiment_confidence"] for r in records]
        df_scored["p_pos"] = [r["p_pos"] for r in records]
        df_scored["p_neg"] = [r["p_neg"] for r in records]
        df_scored["p_neu"] = [r["p_neu"] for r in records]
        return df_scored
