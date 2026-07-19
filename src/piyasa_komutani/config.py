"""config.toml'dan tek deger okuma yardimcisi.

Config her zaman opsiyoneldir: dosya/bolum/anahtar yoksa ya da TOML
bozuksa hicbir zaman exception firlatilmaz, cagiranin verdigi
varsayilana sessizce dusulur.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def load_toml_value(config_path: Path, section: str, key: str, default: T) -> T:
    """config.toml'dan [section].key okur; okunamazsa default doner."""
    try:
        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)
        value = config[section][key]
        return type(default)(value)
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        return default
