"""SentimentLabel, SentimentResult, SentimentProvider ve analyze_articles testleri."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import get_args

import pytest

from piyasa_komutani.news import NewsArticle
from piyasa_komutani.sentiment import (
    NullSentimentProvider,
    SentimentLabel,
    SentimentProvider,
    SentimentResult,
    analyze_articles,
)


def test_sentiment_label_values() -> None:
    assert get_args(SentimentLabel) == ("POSITIVE", "NEUTRAL", "NEGATIVE")


def test_creates_sentiment_result() -> None:
    article = NewsArticle(
        symbol="THYAO.IS",
        title="Test haberi",
        source="Test",
        published_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc),
        url="https://example.com/test",
        summary="Test ozeti.",
    )
    result = SentimentResult(
        article=article,
        label="POSITIVE",
        score=0.75,
    )

    assert result.article == article
    assert result.label == "POSITIVE"
    assert result.score == 0.75
    assert result.confidence is None


def test_creates_sentiment_result_with_confidence() -> None:
    article = NewsArticle(
        symbol="ASELS.IS",
        title="Test haberi 2",
        source="Foreks",
        published_at=datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc),
        url="https://example.com/test2",
        summary="Test ozeti 2.",
    )
    result = SentimentResult(
        article=article,
        label="NEGATIVE",
        score=-0.45,
        confidence=0.88,
    )

    assert result.label == "NEGATIVE"
    assert result.score == -0.45
    assert result.confidence == 0.88


def test_sentiment_result_is_immutable() -> None:
    article = NewsArticle(
        symbol="THYAO.IS",
        title="Test",
        source="Test",
        published_at=datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc),
        url="https://example.com/t",
        summary="Test.",
    )
    result = SentimentResult(article=article, label="NEUTRAL", score=0.0)

    with pytest.raises(AttributeError):
        result.score = 1.0  # type: ignore[misc]


class _FakeProvider:
    """SentimentProvider Protocol'u icin fake implementasyon."""

    def __init__(self, name: str = "fake") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def analyze(self, article: NewsArticle) -> SentimentResult:
        return SentimentResult(
            article=article,
            label="NEUTRAL",
            score=0.0,
            confidence=None,
        )


class _MissingAnalyze:
    """SentimentProvider Protocol'unu karsilamayan sinif."""

    @property
    def name(self) -> str:
        return "missing"


class _MissingName:
    """SentimentProvider Protocol'unu karsilamayan sinif."""

    def analyze(self, article: NewsArticle) -> SentimentResult:
        return SentimentResult(
            article=article, label="NEUTRAL", score=0.0
        )


def test_sentiment_provider_is_runtime_checkable() -> None:
    provider = _FakeProvider()
    assert isinstance(provider, SentimentProvider)


def test_sentiment_provider_rejects_missing_analyze() -> None:
    assert not isinstance(_MissingAnalyze(), SentimentProvider)


def test_sentiment_provider_rejects_missing_name() -> None:
    assert not isinstance(_MissingName(), SentimentProvider)


def test_analyze_articles_returns_results_for_all() -> None:
    published = datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc)
    articles = [
        NewsArticle(
            symbol=f"SYM{i}",
            title=f"Haber {i}",
            source="Test",
            published_at=published,
            url=f"https://example.com/{i}",
            summary=f"Ozet {i}.",
        )
        for i in range(3)
    ]
    provider = _FakeProvider()
    results = analyze_articles(provider, articles)

    assert len(results) == 3
    assert all(r.label == "NEUTRAL" for r in results)
    assert all(r.article is a for r, a in zip(results, articles, strict=True))


def test_sentiment_provider_name_is_accessible() -> None:
    provider = _FakeProvider(name="vader-test")
    assert provider.name == "vader-test"


def test_null_provider_has_fixed_name() -> None:
    assert NullSentimentProvider().name == "null"


def test_null_provider_returns_neutral() -> None:
    article = NewsArticle(
        symbol="THYAO.IS",
        title="Test",
        source="Test",
        published_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc),
        url="https://example.com/t",
        summary="Test.",
    )
    result = NullSentimentProvider().analyze(article)

    assert result.label == "NEUTRAL"
    assert result.score == 0.0
    assert result.confidence is None


def test_null_provider_is_runtime_compatible_without_inheritance() -> None:
    provider = NullSentimentProvider()
    assert isinstance(provider, SentimentProvider)
    assert SentimentProvider not in type(provider).__mro__


def test_null_provider_with_analyze_articles() -> None:
    published = datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc)
    articles = [
        NewsArticle(symbol=f"SYM{i}", title=f"H {i}", source="T",
                     published_at=published, url=f"https://e.com/{i}",
                     summary=f"S {i}.")
        for i in range(2)
    ]
    results = analyze_articles(NullSentimentProvider(), articles)
    assert len(results) == 2
    assert all(r.label == "NEUTRAL" for r in results)


def test_sentiment_result_equality_and_hash() -> None:
    article = NewsArticle(
        symbol="THYAO.IS",
        title="Esitlik testi",
        source="Test",
        published_at=datetime(2026, 7, 20, 15, 0, 0, tzinfo=timezone.utc),
        url="https://example.com/esit",
        summary="Ayni icerik.",
    )
    r1 = SentimentResult(article=article, label="POSITIVE", score=0.5, confidence=0.9)
    r2 = SentimentResult(article=article, label="POSITIVE", score=0.5, confidence=0.9)

    assert r1 == r2
    assert hash(r1) == hash(r2)
