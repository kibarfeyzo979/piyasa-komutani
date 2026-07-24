"""v0.8: veri modeli + analiz ara yuzu, analiz mantigi yok.

SentimentLabel ve SentimentResult veri modellerini, SentimentProvider
Protocol'u ve analyze_articles yardimcisini tanimlar. Somut analyzer
siniflari bu modulde degil, provider'i implemente eden ayri
modullerde yasayacak.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from piyasa_komutani.news import NewsArticle

SentimentLabel = Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]


@dataclass(frozen=True)
class SentimentResult:
    """Bir NewsArticle uzerindeki duyarlilik analizi sonucu.

    Alanlar:
        article:    Analiz edilen haber.
        label:      Siniflandirma sonucu (POSITIVE/NEUTRAL/NEGATIVE).
        score:      -1.0 ile +1.0 arasi n sayisal puan.
        confidence: Modelin guven skoru (0.0-1.0), opsiyonel.
    """

    article: NewsArticle
    label: SentimentLabel
    score: float
    confidence: float | None = None


@runtime_checkable
class SentimentProvider(Protocol):
    """Duyarlilik analizi saglayicisi icin arayuz.

    name:      Saglayici tanimlayici (ornek: "vader", "finbert").
    analyze:   Tek bir NewsArticle'i analiz edip SentimentResult doner.
    """

    @property
    def name(self) -> str: ...

    def analyze(self, article: NewsArticle) -> SentimentResult: ...


class NullSentimentProvider:
    """Hicbir sey yapmayan SentimentProvider (null-object pattern).

    Tum girdileri NEUTRAL/0.0 olarak isaretler. Provider'in hazir
    olmadigi ya da devre disi birakildigi durumlarda kullanilir.
    SentimentProvider'dan kalitim almaz, yapisal uyumluluga guvenir.
    """

    @property
    def name(self) -> str:
        return "null"

    def analyze(self, article: NewsArticle) -> SentimentResult:
        return SentimentResult(
            article=article,
            label="NEUTRAL",
            score=0.0,
            confidence=None,
        )


def analyze_articles(
    provider: SentimentProvider,
    articles: Iterable[NewsArticle],
) -> list[SentimentResult]:
    """Birden cok haberi sirayla analiz eder."""
    return [provider.analyze(a) for a in articles]
