"""Comprehensive unit tests for entity linking, cashtag parsing, and broadcast rules."""

import pytest
from src.nlp.entity_linking import EntityLinker, CONFIDENCE_TABLE


@pytest.fixture(scope="module")
def linker():
    return EntityLinker()


# ============================================================================
# 1. Tricky Ambiguity and Disambiguation Test Cases
# ============================================================================

def test_apple_pie_recipe_no_match(linker):
    """'Apple pie recipe' should not link to AAPL."""
    res = linker.link("Grandma's secret apple pie recipe with cinnamon", source="newsapi")
    assert "AAPL" not in res["linked_tickers"]
    assert res["is_relevant"] is False


def test_apple_unveils_iphone_matches_aapl(linker):
    """'Apple unveils new iPhone' should link to AAPL via company name and product."""
    res = linker.link("Apple unveils new iPhone with faster processor", source="newsapi")
    assert "AAPL" in res["linked_tickers"]
    assert res["primary_ticker"] == "AAPL"
    assert res["is_relevant"] is True


def test_pg13_movie_no_match(linker):
    """'PG-13 movie' should not match Procter & Gamble."""
    res = linker.link("The new superhero blockbuster was rated PG-13 by the MPAA", source="newsapi")
    assert "PG" not in res["linked_tickers"]


def test_pg_cashtag_matches_pg(linker):
    """'$PG earnings beat' should match PG via cashtag."""
    res = linker.link("$PG earnings beat expectations this morning", source="twitter")
    assert res["primary_ticker"] == "PG"
    assert res["link_type"] == "cashtag"
    assert res["link_confidence"] == CONFIDENCE_TABLE["cashtag"]


def test_procter_and_gamble_matches_pg(linker):
    """'Procter & Gamble raises prices' should match PG via full company name."""
    res = linker.link("Procter & Gamble raises consumer prices on detergent", source="newsapi")
    assert res["primary_ticker"] == "PG"
    assert res["link_type"] == "company_name"


def test_meta_platforms_layoffs_matches_meta(linker):
    """'Meta Platforms layoffs' should match META."""
    res = linker.link("Meta Platforms announces restructuring and workforce layoffs", source="newsapi")
    assert res["primary_ticker"] == "META"
    assert res["link_type"] == "company_name"


def test_she_is_meta_no_match(linker):
    """'she is meta about it' should not match META."""
    res = linker.link("She is really meta about her artistic process and novel", source="newsapi")
    assert "META" not in res["linked_tickers"]


def test_knockout_ko_no_match(linker):
    """'knockout KO in round 2' should not match Coca-Cola."""
    res = linker.link("The boxer delivered a stunning knockout KO in round 2 of the championship fight", source="newsapi")
    assert "KO" not in res["linked_tickers"]


def test_coca_cola_shares_rise_matches_ko(linker):
    """'Coca-Cola shares rise' should match KO."""
    res = linker.link("Coca-Cola shares rise after strong international beverage sales", source="newsapi")
    assert res["primary_ticker"] == "KO"
    assert res["link_type"] == "company_name"


def test_cost_of_living_no_match(linker):
    """'the cost of living' should not match Costco."""
    res = linker.link("The cost of living crisis is putting pressure on household savings", source="newsapi")
    assert "COST" not in res["linked_tickers"]


def test_costco_membership_fees_matches_cost(linker):
    """'Costco membership fees' should match COST."""
    res = linker.link("Costco membership fees are set to rise next fiscal quarter", source="newsapi")
    assert res["primary_ticker"] == "COST"


def test_cost_cashtag_matches_cost(linker):
    """'$COST' should match COST via cashtag."""
    res = linker.link("Adding more $COST to our long-term portfolio today", source="twitter")
    assert res["primary_ticker"] == "COST"
    assert res["link_type"] == "cashtag"


def test_amazon_rainforest_fires_no_match(linker):
    """'Amazon rainforest fires' should not match AMZN."""
    res = linker.link("Severe droughts cause widespread Amazon rainforest fires in Brazil", source="newsapi")
    assert "AMZN" not in res["linked_tickers"]


def test_aws_outage_hits_amazon_matches_amzn(linker):
    """'AWS outage hits Amazon' should match AMZN via product and company context."""
    res = linker.link("A major AWS outage hits Amazon cloud customers worldwide", source="newsapi")
    assert res["primary_ticker"] == "AMZN"


def test_boeing_737_recall_matches_ba(linker):
    """'Boeing 737 recall' should match BA via company name and product."""
    res = linker.link("FAA orders inspection for Boeing 737 aircraft fleet", source="newsapi")
    assert res["primary_ticker"] == "BA"


def test_tesla_coil_physics_no_match(linker):
    """'Tesla coil physics' should not match TSLA."""
    res = linker.link("Students demonstrated high voltage sparks using a classic Tesla coil in physics lab", source="newsapi")
    assert "TSLA" not in res["linked_tickers"]


def test_fed_raises_rates_sp500_falls_matches_market(linker):
    """'Fed raises rates, S&P 500 falls' should match MARKET."""
    res = linker.link("Fed raises interest rates by 25 basis points as S&P 500 falls sharply", source="newsapi")
    assert res["primary_ticker"] == "MARKET"


def test_multi_company_headlines(linker):
    """Multi-company headline should link all mentioned companies."""
    res = linker.link("Apple and Microsoft shares rise on joint enterprise AI initiative", source="newsapi")
    assert "AAPL" in res["linked_tickers"]
    assert "MSFT" in res["linked_tickers"]


# ============================================================================
# 2. Real Tweets & Broadcast Tests
# ============================================================================

def test_real_tweet_1_broadcast(linker):
    """$MSFT $AMZN $SNOW $GOOGL $ORCL (hint PG): linked [AMZN, GOOGL, MSFT], PG NOT linked, broadcast."""
    text = "$MSFT $AMZN $SNOW $GOOGL $ORCL"
    res = linker.link(text, ticker_hint="PG", source="twitter")
    assert set(res["linked_tickers"]) == {"MSFT", "AMZN", "GOOGL"}
    assert "PG" not in res["linked_tickers"]
    assert res["n_linked_tickers"] == 3
    assert res["is_broadcast"] is True
    assert res["primary_ticker"] is None
    assert set(res["other_cashtags"]) == {"SNOW", "ORCL"}


def test_real_tweet_2_single_ticker(linker):
    """This Bezos quote about $AMZN also applies to investing... (hint MSFT): linked [AMZN], primary AMZN, MSFT NOT linked."""
    text = "This Bezos quote about $AMZN also applies to investing..."
    res = linker.link(text, ticker_hint="MSFT", source="twitter")
    assert res["linked_tickers"] == ["AMZN"]
    assert res["primary_ticker"] == "AMZN"
    assert "MSFT" not in res["linked_tickers"]
    assert res["n_linked_tickers"] == 1
    assert res["is_broadcast"] is False


def test_real_tweet_3_broadcast(linker):
    """The fact $AMZN $AAPL $TSLA haven't made 52 week lows... (hint TSLA): broadcast."""
    text = "The fact $AMZN $AAPL $TSLA haven't made 52 week lows..."
    res = linker.link(text, ticker_hint="TSLA", source="twitter")
    assert res["is_broadcast"] is True
    assert res["primary_ticker"] is None
    assert res["n_linked_tickers"] == 3


def test_real_tweet_4_fb_alias_and_other_cashtags(linker):
    """The pace of Q1 reporting is ramping up! ... $KO $GOOGL $MSFT $V $FB $AMZN $AAPL $MCD $MRK and $CVX... (hint AAPL): META present via $FB, broadcast."""
    text = "The pace of Q1 reporting is ramping up! ... $KO $GOOGL $MSFT $V $FB $AMZN $AAPL $MCD $MRK and $CVX..."
    res = linker.link(text, ticker_hint="AAPL", source="twitter")
    assert "META" in res["linked_tickers"]
    assert res["is_broadcast"] is True
    assert res["primary_ticker"] is None
    for ot in ["V", "MCD", "MRK", "CVX"]:
        assert ot in res["other_cashtags"]


def test_real_tweet_5_brk_b_ignored(linker):
    """Diversify your portfolio 25% Blue Chip $AAPL $GOOGL $FB $AMZN $BRK.B $MSFT... (hint PYPL): broadcast, BRK.B ignored."""
    text = "Diversify your portfolio 25% Blue Chip $AAPL $GOOGL $FB $AMZN $BRK.B $MSFT..."
    res = linker.link(text, ticker_hint="PYPL", source="twitter")
    assert res["is_broadcast"] is True
    assert "BRK.B" in res["other_cashtags"]
    assert "BRK.B" not in res["linked_tickers"]


def test_real_tweet_6_spy_with_broadcast(linker):
    """$SPY All we can see in the week ahead... $MSFT $BA $AAPL & $TSLA earnings (hint BA): broadcast, and SPY must not become the primary."""
    text = "$SPY All we can see in the week ahead... $MSFT $BA $AAPL & $TSLA earnings"
    res = linker.link(text, ticker_hint="BA", source="twitter")
    assert res["is_broadcast"] is True
    assert res["primary_ticker"] is None
    assert "MARKET" in res["linked_tickers"]


def test_real_tweet_7_spy_and_single_company(linker):
    """Both $SPY and $AAPL breaking trends on the daily (hint AAPL): primary AAPL with a macro tag."""
    text = "Both $SPY and $AAPL breaking trends on the daily"
    res = linker.link(text, ticker_hint="AAPL", source="twitter")
    assert res["primary_ticker"] == "AAPL"
    assert "MARKET" in res["linked_tickers"]
    assert res["n_linked_tickers"] == 1
    assert res["is_broadcast"] is False


def test_real_tweet_8_other_cashtags_and_broadcast(linker):
    """HOW TO use @unusual_whales Bullish Candle Combo ... $UPST ... Chart @TrendSpider $NVDA $AMD $ROKU $TSLA (hint TSLA): broadcast, UPST and ROKU in other_cashtags."""
    text = "HOW TO use @unusual_whales Bullish Candle Combo ... $UPST ... Chart @TrendSpider $NVDA $AMD $ROKU $TSLA"
    res = linker.link(text, ticker_hint="TSLA", source="twitter")
    assert res["is_broadcast"] is True
    assert "UPST" in res["other_cashtags"]
    assert "ROKU" in res["other_cashtags"]


def test_real_tweet_9_spy_breaking_down(linker):
    """$SPY is breaking down: primary MARKET."""
    res = linker.link("$SPY is breaking down", source="twitter")
    assert res["primary_ticker"] == "MARKET"
    assert res["n_linked_tickers"] == 0
    assert res["attribution_weight"] == 1.0


# ============================================================================
# 3. Cashtag Edge Cases & Formatting Tests
# ============================================================================

@pytest.mark.parametrize("amt_text", ["$5bn", "$10M", "$1.2B", "$100", "$USD"])
def test_dollar_amounts_and_currencies_not_cashtags(linker, amt_text):
    """Verify dollar amounts and currency codes are not treated as cashtags."""
    res = linker.link(f"Total revenue reached {amt_text} this quarter", source="twitter")
    assert len(res["linked_tickers"]) == 0
    assert len(res["other_cashtags"]) == 0


def test_glued_cashtag_etf_voo(linker):
    """Glued text like ETF$VOO $VIG $VGT should record VOO, VIG, VGT in other_cashtags."""
    text = "Best long term holdings: ETF$VOO $VIG $VGT for steady growth"
    res = linker.link(text, source="twitter")
    for tag in ["VOO", "VIG", "VGT"]:
        assert tag in res["other_cashtags"]


def test_case_insensitive_brkb_and_tsla(linker):
    """Verify $brk.b and $tsla match case-insensitively."""
    text = "Holding both $brk.b and $tsla long term"
    res = linker.link(text, source="twitter")
    assert "BRK.B" in res["other_cashtags"]
    assert "TSLA" in res["linked_tickers"]
    assert res["primary_ticker"] == "TSLA"


# ============================================================================
# 4. Hint-Only and Two-Ticker Resolution Tests
# ============================================================================

def test_hint_only_tweet_no_evidence(linker):
    """Hint-only tweet with no tickers or company names: hint wins with confidence 0.4."""
    text = "Great day for the markets across the board"
    res = linker.link(text, ticker_hint="KO", source="twitter")
    assert res["linked_tickers"] == ["KO"]
    assert res["primary_ticker"] == "KO"
    assert res["link_type"] == "hint_only"
    assert res["link_confidence"] == 0.40
    assert res["n_linked_tickers"] == 1
    assert res["attribution_weight"] == 1.0


def test_two_ticker_tweet_hint_present_wins(linker):
    """Two-ticker tweet where hint is one of them: hint wins."""
    text = "$AAPL is outperforming $MSFT today"
    res = linker.link(text, ticker_hint="MSFT", source="twitter")
    assert res["n_linked_tickers"] == 2
    assert res["primary_ticker"] == "MSFT"
    assert res["is_broadcast"] is False
    assert res["attribution_weight"] == 0.5


def test_two_ticker_tweet_hint_not_present_most_mentioned_wins(linker):
    """Two-ticker tweet where hint is not one of them: most-mentioned wins."""
    text = "$AAPL is soaring, adding more $AAPL calls, while $MSFT lags"
    res = linker.link(text, ticker_hint="KO", source="twitter")
    assert res["n_linked_tickers"] == 2
    assert res["primary_ticker"] == "AAPL"
    assert res["is_broadcast"] is False
    assert res["attribution_weight"] == 0.5


def test_two_ticker_tweet_hint_not_present_earliest_wins_on_tie(linker):
    """Two-ticker tweet where hint is not one of them and equal mentions: earliest wins."""
    text = "$MSFT and $AAPL report earnings next week"
    res = linker.link(text, ticker_hint="KO", source="twitter")
    assert res["n_linked_tickers"] == 2
    assert res["primary_ticker"] == "MSFT"
    assert res["is_broadcast"] is False
    assert res["attribution_weight"] == 0.5
