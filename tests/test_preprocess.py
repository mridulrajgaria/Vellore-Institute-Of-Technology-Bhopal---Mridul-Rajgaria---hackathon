"""Unit tests for text preprocessing, publisher suffix stripping, and token spacing fixes."""

import pytest

from src.nlp.preprocess import clean_for_model, fix_token_spacing, strip_publisher_suffix


def test_fix_token_spacing_real_data_cases():
    """Verify all real-data token spacing cases specified in requirements."""
    assert fix_token_spacing("word . Next") == "word. Next"
    assert fix_token_spacing("vs .") == "vs."
    assert fix_token_spacing("bail - outs") == "bail-outs"
    assert fix_token_spacing("all - out") == "all-out"
    assert fix_token_spacing(" , ") == ", "
    assert fix_token_spacing("$17 , 500") == "$17,500"
    assert fix_token_spacing("$32 . 5") == "$32.5"


def test_fix_token_spacing_additional_punctuation():
    """Verify punctuation spacing around commas, question marks, and colons."""
    assert fix_token_spacing("apple , banana , cherry") == "apple, banana, cherry"
    assert fix_token_spacing("Is this real ? Yes .") == "Is this real? Yes."
    assert fix_token_spacing("GOLDSTEIN : Job losses") == "GOLDSTEIN: Job losses"


def test_strip_publisher_suffix_success():
    """Verify trailing publisher suffixes with no finance verbs are cleanly stripped."""
    assert strip_publisher_suffix("Apple Unveils New Device - Bloomberg") == "Apple Unveils New Device"
    assert strip_publisher_suffix("Fed Pauses Rate Hikes – The Wall Street Journal") == "Fed Pauses Rate Hikes"
    assert strip_publisher_suffix("Microsoft Cloud Revenue Expands | Reuters") == "Microsoft Cloud Revenue Expands"
    assert strip_publisher_suffix("Tesla Expands Supercharger Network — CNBC") == "Tesla Expands Supercharger Network"


def test_strip_publisher_suffix_preserves_content_with_finance_verbs():
    """Verify trailing clauses containing verbs or financial topics are NOT stripped."""
    # Contains 'drops' and 'profit'
    headline = "Tech stocks tumble - profit drops across sector"
    assert strip_publisher_suffix(headline) == headline

    # Contains 'surged' and 'earnings'
    headline_2 = "Retail sector rallies – earnings surged in Q3"
    assert strip_publisher_suffix(headline_2) == headline_2


def test_strip_publisher_suffix_preserves_long_suffixes():
    """Verify suffixes with 8 or more words are not stripped as site names."""
    long_suffix = "Major Market Analysis - this is an in-depth long piece of commentary with many words"
    assert strip_publisher_suffix(long_suffix) == long_suffix


def test_clean_for_model_tweets():
    """Verify tweet cleaning for model: cashtags stripped to symbols, amounts preserved, whitespace collapsed."""
    # Cashtags stripped for model input
    text = "$TSLA reaches record high while $AAPL holds steady"
    cleaned = clean_for_model(text, source="twitter_kaggle")
    assert "TSLA reaches record high while AAPL holds steady" == cleaned

    # Glued cashtag
    text_glued = "Buying ETF$VOO today"
    assert "Buying ETF VOO today" == clean_for_model(text_glued, source="twitter_kaggle")

    # Dollar amounts and currency codes preserved with dollar sign
    text_amounts = "Allocating $5bn and $10M or $100 to $TSLA"
    cleaned_amounts = clean_for_model(text_amounts, source="twitter_kaggle")
    assert "$5bn" in cleaned_amounts
    assert "$10M" in cleaned_amounts
    assert "$100" in cleaned_amounts
    assert "TSLA" in cleaned_amounts
    assert "$TSLA" not in cleaned_amounts


def test_clean_for_model_gdelt_and_newsapi():
    """Verify GDELT and NewsAPI texts undergo publisher stripping, spacing fix, and whitespace collapsing."""
    raw = "GOLDSTEIN : Job losses , inflation and bail - outs - Bloomberg"
    cleaned = clean_for_model(raw, source="gdelt")
    assert cleaned == "GOLDSTEIN: Job losses, inflation and bail-outs"


def test_clean_for_model_word_cap():
    """Verify text is capped at 128 words for model input."""
    long_text = " ".join([f"word{i}" for i in range(200)])
    cleaned = clean_for_model(long_text)
    words = cleaned.split()
    assert len(words) == 128
    assert words[0] == "word0"
    assert words[-1] == "word127"
