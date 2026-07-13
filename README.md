# Piyasa Komutani

Basit bir yatirim analiz uygulamasi. BIST hisseleri icin fiyat verisi cekip
EMA, RSI ve MACD gostergelerini hesaplar, kural tabanli basit bir "firsat
puani" uretir ve sonuclari bir Excel dosyasina yazar.

> Durum: proje iskelet asamasinda. Veri cekme ve indikator/puan hesaplama
> mantigi henuz uygulanmadi.

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

## Test

```
uv run pytest
```

## Proje Yapisi

```
piyasa-komutani/
├── main.py                  # CLI giris noktasi
├── config.toml               # veri kaynagi, indikator ve ciktiya dair ayarlar
├── portfolio.csv              # ornek sembol listesi (symbol, name)
├── src/piyasa_komutani/
│   ├── data.py                # sembol listesi okuma + fiyat verisi alma
│   ├── indicators.py          # EMA, RSI, MACD hesaplama
│   ├── scoring.py              # firsat puani hesaplama
│   └── export.py               # Excel'e yazma
├── tests/                      # birim testleri
└── output/                     # uretilen Excel ciktilari (git'e dahil degil)
```

## 1. Asama Yol Haritasi

1. `portfolio.csv`'den sembol listesini okuma
2. yfinance ile BIST fiyat verisi cekme
3. EMA, RSI, MACD hesaplama
4. Basit, kural tabanli firsat puani uretme
5. Sonuclari `output/sonuclar.xlsx` dosyasina yazma
