"""Unit tests for FinBERT sentiment scoring, dynamic id2label mapping, and disk caching."""

from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
import torch

from src.nlp.sentiment import FinBertScorer


class DummyTokenizer:
    """Mock tokenizer returning PyTorch tensor dict."""

    def __call__(self, texts, padding=True, truncation=True, max_length=128, return_tensors="pt"):
        n = len(texts)
        return {
            "input_ids": torch.ones((n, 10), dtype=torch.long),
            "attention_mask": torch.ones((n, 10), dtype=torch.long),
        }


def make_mock_model(id2label_dict, logits_list):
    """Create a mock model returning predefined logits and specified id2label mapping."""
    mock_model = MagicMock()
    mock_model.config = SimpleNamespace(id2label=id2label_dict)
    mock_model.eval = MagicMock()

    logits_tensor = torch.tensor(logits_list, dtype=torch.float32)

    def forward_fn(**kwargs):
        input_ids = kwargs.get("input_ids")
        batch_size = input_ids.shape[0] if input_ids is not None else len(logits_list)
        # Repeat or slice to match batch_size
        batch_logits = logits_tensor[:batch_size]
        return SimpleNamespace(logits=batch_logits)

    mock_model.side_effect = forward_fn
    return mock_model


def test_dynamic_label_order_permuted():
    """Verify that when id2label is permuted {0: neutral, 1: positive, 2: negative},

    sentiment_score = p_pos - p_neg still holds precisely.
    """
    # id2label with neutral at 0, positive at 1, negative at 2
    id2label = {0: "neutral", 1: "positive", 2: "negative"}

    # Raw logits: [neu=0.0, pos=3.0, neg=1.0]
    logits = [[0.0, 3.0, 1.0]]
    mock_model = make_mock_model(id2label, logits)
    tokenizer = DummyTokenizer()

    scorer = FinBertScorer(model=mock_model, tokenizer=tokenizer, cache_path=None)

    assert scorer.pos_idx == 1
    assert scorer.neg_idx == 2
    assert scorer.neu_idx == 0

    results = scorer.score_texts(["Strong profit growth reported"])
    assert len(results) == 1
    res = results[0]

    # Calculate expected softmax
    expected_probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()[0]
    exp_neu = expected_probs[0]
    exp_pos = expected_probs[1]
    exp_neg = expected_probs[2]

    assert pytest.approx(res["p_pos"], abs=1e-5) == exp_pos
    assert pytest.approx(res["p_neg"], abs=1e-5) == exp_neg
    assert pytest.approx(res["p_neu"], abs=1e-5) == exp_neu
    assert pytest.approx(res["sentiment_score"], abs=1e-5) == (exp_pos - exp_neg)
    assert res["sentiment_label"] == "positive"
    assert pytest.approx(res["sentiment_confidence"], abs=1e-5) == exp_pos


def test_dynamic_label_order_inverted():
    """Verify inverted id2label order: {0: negative, 1: neutral, 2: positive}."""
    id2label = {0: "negative", 1: "neutral", 2: "positive"}

    # Raw logits: [neg=4.0, neu=1.0, pos=0.0]
    logits = [[4.0, 1.0, 0.0]]
    mock_model = make_mock_model(id2label, logits)
    tokenizer = DummyTokenizer()

    scorer = FinBertScorer(model=mock_model, tokenizer=tokenizer, cache_path=None)

    assert scorer.neg_idx == 0
    assert scorer.neu_idx == 1
    assert scorer.pos_idx == 2

    results = scorer.score_texts(["Company suffers catastrophic bankruptcy"])
    res = results[0]

    expected_probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()[0]
    exp_neg = expected_probs[0]
    exp_neu = expected_probs[1]
    exp_pos = expected_probs[2]

    assert pytest.approx(res["p_neg"], abs=1e-5) == exp_neg
    assert pytest.approx(res["p_pos"], abs=1e-5) == exp_pos
    assert pytest.approx(res["sentiment_score"], abs=1e-5) == (exp_pos - exp_neg)
    assert res["sentiment_label"] == "negative"
    assert res["sentiment_score"] < 0.0


def test_score_range_bounds():
    """Verify that sentiment_score is strictly in [-1.0, 1.0] and probabilities sum to 1.0."""
    id2label = {0: "positive", 1: "negative", 2: "neutral"}
    logits = [[10.0, -5.0, 0.0], [-10.0, 10.0, 0.0], [0.0, 0.0, 10.0]]
    mock_model = make_mock_model(id2label, logits)
    tokenizer = DummyTokenizer()

    scorer = FinBertScorer(model=mock_model, tokenizer=tokenizer, cache_path=None)
    results = scorer.score_texts(["Great", "Awful", "Unchanged"])

    for r in results:
        assert -1.0 <= r["sentiment_score"] <= 1.0
        assert 0.0 <= r["sentiment_confidence"] <= 1.0
        assert pytest.approx(r["p_pos"] + r["p_neg"] + r["p_neu"], abs=1e-5) == 1.0


def test_cache_hits_and_persistence(tmp_path):
    """Verify that cached texts are loaded from cache and do not invoke the model forward pass."""
    cache_file = tmp_path / "test_cache.parquet"

    id2label = {0: "positive", 1: "negative", 2: "neutral"}
    mock_model = make_mock_model(id2label, [[2.0, 0.0, 1.0]])
    tokenizer = DummyTokenizer()

    scorer_1 = FinBertScorer(model=mock_model, tokenizer=tokenizer, cache_path=cache_file)
    res_1 = scorer_1.score_texts(["Company revenue increases"])
    assert mock_model.call_count == 1
    assert cache_file.exists()

    # Second run with new scorer instance pointing to same cache file
    mock_model_2 = make_mock_model(id2label, [[0.0, 0.0, 0.0]])
    scorer_2 = FinBertScorer(model=mock_model_2, tokenizer=tokenizer, cache_path=cache_file)
    res_2 = scorer_2.score_texts(["Company revenue increases"])

    # Model 2 must NOT be called because it was served from cache!
    assert mock_model_2.call_count == 0
    assert pytest.approx(res_1[0]["sentiment_score"], abs=1e-5) == res_2[0]["sentiment_score"]


def test_empty_text_returns_neutral():
    """Verify empty or blank texts return neutral defaults without error."""
    id2label = {0: "positive", 1: "negative", 2: "neutral"}
    mock_model = make_mock_model(id2label, [[1.0, 1.0, 1.0]])
    tokenizer = DummyTokenizer()

    scorer = FinBertScorer(model=mock_model, tokenizer=tokenizer, cache_path=None)
    results = scorer.score_texts(["", "   "])
    for r in results:
        assert r["sentiment_score"] == 0.0
        assert r["sentiment_label"] == "neutral"
        assert r["p_neu"] == 1.0


def test_score_dataframe():
    """Verify score_dataframe appends the 6 expected sentiment columns."""
    id2label = {0: "positive", 1: "negative", 2: "neutral"}
    mock_model = make_mock_model(id2label, [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    tokenizer = DummyTokenizer()

    scorer = FinBertScorer(model=mock_model, tokenizer=tokenizer, cache_path=None)
    df = pd.DataFrame({
        "text": ["Profits soar", "Losses deepen"],
        "source": ["newsapi", "newsapi"],
    })

    scored_df = scorer.score_dataframe(df)
    expected_cols = ["sentiment_score", "sentiment_label", "sentiment_confidence", "p_pos", "p_neg", "p_neu"]
    for col in expected_cols:
        assert col in scored_df.columns
    assert len(scored_df) == 2
    assert scored_df.iloc[0]["sentiment_label"] == "positive"
    assert scored_df.iloc[1]["sentiment_label"] == "negative"
