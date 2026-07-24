# Piyasa Komutani

Basit bir yatirim analiz uygulamasi. Portfoydeki semboller icin fiyat
verisi cekip EMA, RSI ve MACD gostergelerini hesaplar, kural tabanli
basit bir "firsat puani" uretir ve sonuclari bir Excel dosyasina yazar.

> Durum: portfoy okuma, piyasa verisi cekme/cache, teknik analiz (Trend
> Score + Opportunity Score), Position Health Score, evren taramasi ve
> gunluk ozet rapor (Daily Brief) uctan uca calisiyor. v0.8: haber/sentiment
> altyapisi eklendi (veri modeli + arayuz, henuz entegre edilmedi, AI kullanmiyor).

## Gereksinimler

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/)

## Kurulum

```
uv sync
```

## Calistirma

`main.py` tek giris noktasi, dort alt komutu var (argparse, agir bir
CLI framework yok):

```
uv run python main.py portfolio   # veya sadece: uv run python main.py
```

`portfolio.csv`'deki her sembol icin piyasa verisini cache'ler (veya
gerekirse gunceller), indikatorleri ve firsat puanini hesaplar,
sonuclari `output/sonuclar.xlsx` dosyasina yazar ve ozet bir tablo
ekrana basar. `portfolio` argumani opsiyonel - varsayilan komut budur.

```
uv run python main.py scan
```

`data/universe.csv`'deki (portfoyden bagimsiz) `enabled=true`
sembolleri tarar, likidite filtresinden gecen adaylari Firsat
Skoru'na gore siralar, ilk 10'u ekrana basar ve tum sonuclari
`reports/opportunities.csv`'ye yazar. AL/SAT onerisi uretmez -
yalnizca teknik acidan guclu adaylari siralar.

```
uv run python main.py analyze
```

Portfoydeki her pozisyon icin Position Health Score, yogunlasma riski
ve scanner'daki firsatlarla karsilastirma uretir; sonuclari
`reports/portfolio_analysis.csv` ve `reports/portfolio_summary.json`'a yazar.

```
uv run python main.py daily
```

Portfoy analizini ve evren taramasini tek bir gunluk raporda birlestirir
(Portfolio Summary, Risk Alerts, Positions to Review, Strong Positions,
Top Opportunities, Alternative Candidates, Daily Summary). Iki adim
birbirinden bagimsiz calisir - biri basarisiz olsa da digeri rapor
uretmeye devam eder. Sonuclari `reports/daily_brief.json/.csv/.md`'ye yazar.

## Test

```
uv run pytest
```

## Proje Yapisi

```
piyasa-komutani/
├── main.py                  # tek CLI giris noktasi (argparse): portfolio / scan / analyze / daily alt komutlari
├── config.toml               # veri kaynagi, indikator, tarayici, yogunlasma ve daily_brief ayarlari
├── portfolio.csv              # portfoy: symbol, asset_type, quantity, average_cost, currency
├── src/piyasa_komutani/
│   ├── config.py               # config.toml okuma yardimcisi (load_toml_value)
│   ├── data.py                # portfoy + evren CSV okuma/dogrulama
│   ├── market_data.py          # yfinance ile OHLCV fiyat verisi cekme + cache
│   ├── indicators.py          # EMA, RSI, MACD, ortalama hacim hesaplama
│   ├── scoring.py              # firsat puani hesaplama (-3..+3, AL/SAT/NOTR)
│   ├── technical_analysis.py  # EMA20/50/200 + Trend Score + Opportunity Score
│   ├── opportunity_scanner.py # evren taramasi (portfoyden bagimsiz)
│   ├── portfolio_analysis.py  # Position Health Score, yogunlasma riski, scanner karsilastirmasi
│   ├── daily_brief.py          # portfoy + scanner + risk uyarilarini tek gunluk raporda birlestirir
│   ├── news.py                 # v0.8: NewsArticle veri modeli (fetch/kazima yok)
│   ├── sentiment.py            # v0.8: SentimentResult + SentimentProvider arayuzu (analiz mantigi yok)
│   ├── export.py               # Excel'e yazma
│   └── display.py              # tablolari terminalde gosterme
├── tests/                      # birim testleri
├── data/
│   ├── universe.csv            # tarama evreni: symbol, name, market, enabled
│   └── market_data/            # cache'lenen sembol bazli OHLCV CSV'leri (git'e dahil degil)
├── output/                     # uretilen Excel ciktilari (git'e dahil degil)
└── reports/                    # `scan`/`analyze`/`daily` komutlarinin urettigi rapor dosyalari (git'e dahil degil)
```

## Yol Haritasi

- [x] `portfolio.csv`'den sembol listesini okuma (`data.py`)
- [x] yfinance ile fiyat verisi cekme + yerel cache (`market_data.py`)
- [x] EMA, RSI, MACD hesaplama (`indicators.py`)
- [x] Basit, kural tabanli firsat puani uretme (`scoring.py`)
- [x] Sonuclari `output/sonuclar.xlsx` dosyasina yazma (`export.py`)
- [x] Trend Score + Opportunity Score, evren taramasi (`technical_analysis.py`, `opportunity_scanner.py`)
- [x] Position Health Score + yogunlasma riski (`portfolio_analysis.py`)
- [x] Gunluk ozet rapor: Daily Brief (`daily_brief.py`)
- [x] Haber/sentiment veri modeli + entegrasyon arayuzu (`news.py`, `sentiment.py`) - henuz gercek bir saglayici/CLI entegrasyonu yok
