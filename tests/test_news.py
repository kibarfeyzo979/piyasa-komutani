"""NewsArticle veri modeli testleri."""

from __future__ import annotations

from datetime import datetime, timezone

from piyasa_komutani.news import NewsArticle


def test_creates_article_with_required_fields() -> None:
    published = datetime(2026, 7, 20, 10, 0, 0, tzinfo=timezone.utc)
    article = NewsArticle(
        symbol="THYAO.IS",
        title="Turk Hava Yollari yatirimi haberi",
        source="Bloomberg HT",
        published_at=published,
        url="https://example.com/haber/thyao",
        summary="THYAO yeni bir hat acmayi planliyor.",
    )

    assert article.symbol == "THYAO.IS"
    assert article.title == "Turk Hava Yollari yatirimi haberi"
    assert article.source == "Bloomberg HT"
    assert article.published_at == published
    assert article.url == "https://example.com/haber/thyao"
    assert article.summary == "THYAO yeni bir hat acmayi planliyor."


def test_article_is_immutable() -> None:
    published = datetime(2026, 7, 20, 8, 0, 0, tzinfo=timezone.utc)
    article = NewsArticle(
        symbol="THYAO.IS",
        title="Test haberi",
        source="Test",
        published_at=published,
        url="https://example.com/test",
        summary="Test ozeti.",
    )

    import pytest

    with pytest.raises(AttributeError):
        article.title = "Degistirilen baslik"  # type: ignore[misc]


def test_articles_are_equal_when_fields_match() -> None:
    published = datetime(2026, 7, 20, 15, 0, 0, tzinfo=timezone.utc)
    a1 = NewsArticle(
        symbol="THYAO.IS",
        title="Ayni haber",
        source="Kaynak",
        published_at=published,
        url="https://example.com/ayni",
        summary="Ayni detay.",
    )
    a2 = NewsArticle(
        symbol="THYAO.IS",
        title="Ayni haber",
        source="Kaynak",
        published_at=published,
        url="https://example.com/ayni",
        summary="Ayni detay.",
    )

    assert a1 == a2
    assert hash(a1) == hash(a2)
