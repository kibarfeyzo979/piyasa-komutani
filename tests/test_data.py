"""portfolio.csv okuma ve dogrulama testleri."""

from pathlib import Path

from piyasa_komutani.data import PortfolioRow, read_portfolio


def _write_csv(tmp_path: Path, content: str) -> Path:
    csv_path = tmp_path / "portfolio.csv"
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


def test_reads_valid_rows(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        "THYAO.IS,stock,100,285.50,TRY\n"
        "BTC-USD,crypto,0.05,65000,USD\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert errors == []
    assert rows == [
        PortfolioRow("THYAO.IS", "stock", 100.0, 285.50, "TRY"),
        PortfolioRow("BTC-USD", "crypto", 0.05, 65000.0, "USD"),
    ]


def test_empty_symbol_is_rejected(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        ",stock,100,285.50,TRY\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert rows == []
    assert len(errors) == 1
    assert "symbol bos olamaz" in errors[0]


def test_invalid_asset_type_is_rejected(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        "THYAO.IS,bond,100,285.50,TRY\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert rows == []
    assert "asset_type" in errors[0]


def test_zero_or_negative_quantity_is_rejected(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        "THYAO.IS,stock,0,285.50,TRY\n"
        "TUPRS.IS,stock,-5,172.30,TRY\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert rows == []
    assert len(errors) == 2
    assert "quantity negatif veya sifir olamaz" in errors[0]
    assert "quantity negatif veya sifir olamaz" in errors[1]


def test_zero_or_negative_average_cost_is_rejected(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        "THYAO.IS,stock,100,0,TRY\n"
        "TUPRS.IS,stock,40,-172.30,TRY\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert rows == []
    assert len(errors) == 2
    assert "average_cost negatif veya sifir olamaz" in errors[0]
    assert "average_cost negatif veya sifir olamaz" in errors[1]


def test_invalid_currency_is_rejected(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        "THYAO.IS,stock,100,285.50,EUR\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert rows == []
    assert "currency" in errors[0]


def test_invalid_row_does_not_block_other_rows(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "symbol,asset_type,quantity,average_cost,currency\n"
        ",stock,100,285.50,TRY\n"
        "THYAO.IS,stock,100,285.50,TRY\n",
    )

    rows, errors = read_portfolio(csv_path)

    assert len(rows) == 1
    assert rows[0].symbol == "THYAO.IS"
    assert len(errors) == 1
