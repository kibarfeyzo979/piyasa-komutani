# Piyasa Komutani

Basit bir yatirim analiz uygulamasi. Portfoydeki semboller icin fiyat
verisi cekip EMA, RSI ve MACD gostergelerini hesaplar, kural tabanli
basit bir "firsat puani" uretir ve sonuclari bir Excel dosyasina yazar.

> Durum: 1. asama tamamlandi — portfoy okuma, piyasa verisi cekme/cache,
> indikator hesaplama, skorlama ve Excel'e yazma uctan uca calisiyor.

## Gereksinimler

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/)

## Kurulum

```
uv sync
```

## Calistirma

`main.py` tek giris noktasi, iki alt komutu var (argparse, agir bir
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

## Test

```
uv run pytest
```

## Proje Yapisi

```
piyasa-komutani/
├── main.py                  # tek CLI giris noktasi (argparse): portfolio / scan alt komutlari
├── config.toml               # veri kaynagi, indikator ve tarayici ayarlari
├── portfolio.csv              # portfoy: symbol, asset_type, quantity, average_cost, currency
├── src/piyasa_komutani/
│   ├── data.py                # portfoy + evren CSV okuma/dogrulama
│   ├── market_data.py          # yfinance ile OHLCV fiyat verisi cekme + cache
│   ├── indicators.py          # EMA, RSI, MACD, ortalama hacim hesaplama
│   ├── scoring.py              # firsat puani hesaplama (-3..+3, AL/SAT/NOTR)
│   ├── technical_analysis.py  # EMA20/50/200 + 0-100 Opportunity Score
│   ├── opportunity_scanner.py # evren taramasi (portfoyden bagimsiz)
│   ├── export.py               # Excel'e yazma
│   └── display.py              # tablolari terminalde gosterme
├── tests/                      # birim testleri
├── data/
│   ├── universe.csv            # tarama evreni: symbol, name, market, enabled
│   └── market_data/            # cache'lenen sembol bazli OHLCV CSV'leri (git'e dahil degil)
├── output/                     # uretilen Excel ciktilari (git'e dahil degil)
└── reports/                    # `main.py scan`'in urettigi CSV raporlari (git'e dahil degil)
```

## 1. Asama Yol Haritasi

- [x] `portfolio.csv`'den sembol listesini okuma (`data.py`)
- [x] yfinance ile fiyat verisi cekme + yerel cache (`market_data.py`)
- [x] EMA, RSI, MACD hesaplama (`indicators.py`)
- [x] Basit, kural tabanli firsat puani uretme (`scoring.py`)
- [x] Sonuclari `output/sonuclar.xlsx` dosyasina yazma (`export.py`)
