"""v0.8: sadece veri modeli, fetch/kazima yok.

NewsArticle immutable dataclass, dis kaynaklardan (API/RSS) gelen
haberlerin normalize edilmis temsilidir. Sentiment analizi sonucu
burada degil, ayri bir SentimentResult'ta (sentiment.py) tutulur -
ayni bilginin iki yerde tutulup birbirinden kopmasini onlemek icin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsArticle:
    """Tek bir haber maddesini temsil eder.

    Alanlar:
        symbol:        Haberin iliskili oldugu sembol (ornek: THYAO.IS).
        title:         Haber basligi.
        source:        Kaynak adi (ornek: Bloomberg HT, Foreks).
        published_at:  Yayinlanma zamani (UTC).
        url:           Haber linki.
        summary:       Haber ozeti / girisi.
    """

    symbol: str
    title: str
    source: str
    published_at: datetime
    url: str
    summary: str
