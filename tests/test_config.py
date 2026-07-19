"""config.py testleri - gercek ag/dosya erisimi yok, sadece tmp_path."""

from __future__ import annotations

from piyasa_komutani.config import load_toml_value


def test_load_toml_value_reads_existing_value(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[section]\nkey = 42\n", encoding="utf-8")

    assert load_toml_value(config_path, "section", "key", 0) == 42


def test_load_toml_value_falls_back_on_missing_file(tmp_path) -> None:
    missing_path = tmp_path / "does_not_exist.toml"

    assert load_toml_value(missing_path, "section", "key", 99) == 99


def test_load_toml_value_falls_back_on_missing_section(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[other]\nvalue = 1\n", encoding="utf-8")

    assert load_toml_value(config_path, "section", "key", 99) == 99


def test_load_toml_value_falls_back_on_missing_key(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[section]\nother_key = 1\n", encoding="utf-8")

    assert load_toml_value(config_path, "section", "key", 99) == 99


def test_load_toml_value_falls_back_on_malformed_toml(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("bu gecerli bir TOML degil [[[", encoding="utf-8")

    assert load_toml_value(config_path, "section", "key", 99) == 99


def test_load_toml_value_coerces_to_default_type(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[section]\nkey = 42\n", encoding="utf-8")

    result = load_toml_value(config_path, "section", "key", 0.0)

    assert result == 42.0
    assert isinstance(result, float)
