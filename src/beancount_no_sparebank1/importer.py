"""Canonical importer module for SpareBank 1 account statements."""

from .deposit import (
    Config,
    DepositAccountImporter,
    Importer,
    Sparebank1AccountConfig,
    Sparebank1Config,
)

__all__ = [
    "Config",
    "DepositAccountImporter",
    "Importer",
    "Sparebank1AccountConfig",
    "Sparebank1Config",
]
