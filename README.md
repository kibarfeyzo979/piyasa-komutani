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

```
uv run main.py
```

`portfolio.csv`'deki her sembol icin piyasa verisini cache'ler (veya
gerekirse gunceller), indikatorleri ve firsat puanini hesaplar,
sonuclari `output/sonuclar.xlsx` dosyasina yazar ve ozet bir tablo
ekrana basar.

## Test

```
uv run pytest
```

## Proje Yapisi

```
piyasa-komutani/
├── main.py                  # CLI giris noktasi, tum pipeline'i baglar
├── config.toml               # veri kaynagi, indikator ve ciktiya dair ayarlar
├── portfolio.csv              # portfoy: symbol, asset_type, quantity, average_cost, currency
├── src/piyasa_komutani/
│   ├── data.py                # portfoy CSV okuma + dogrulama
│   ├── market_data.py          # yfinance ile OHLCV fiyat verisi cekme + cache
│   ├── indicators.py          # EMA, RSI, MACD hesaplama
│   ├── scoring.py              # firsat puani hesaplama
│   ├── export.py               # Excel'e yazma
│   └── display.py              # portfoy tablosunu terminalde gosterme
├── tests/                      # birim testleri
├── data/market_data/           # cache'lenen sembol bazli OHLCV CSV'leri (git'e dahil degil)
└── output/                     # uretilen Excel ciktilari (git'e dahil degil)
```

## 1. Asama Yol Haritasi

- [x] `portfolio.csv`'den sembol listesini okuma (`data.py`)
- [x] yfinance ile fiyat verisi cekme + yerel cache (`market_data.py`)
- [x] EMA, RSI, MACD hesaplama (`indicators.py`)
- [x] Basit, kural tabanli firsat puani uretme (`scoring.py`)
- [x] Sonuclari `output/sonuclar.xlsx` dosyasina yazma (`export.py`)
