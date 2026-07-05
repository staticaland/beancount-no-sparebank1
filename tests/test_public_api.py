import pytest

from beancount_no_sparebank1 import (
    Config,
    DepositAccountImporter,
    Importer,
    PDFStatementConfig,
    PDFStatementImporter,
    Sparebank1AccountConfig,
    Sparebank1Config,
    StatementConfig,
    StatementImporter,
)
from beancount_no_sparebank1.importer import Config as ModuleConfig
from beancount_no_sparebank1.statement import StatementConfig as ModuleStatementConfig


def test_canonical_importer_api():
    assert ModuleConfig is Config
    assert Sparebank1Config is Config

    importer = Importer(
        Config(
            primary_account_number="12345678901",
            account_name="Assets:Bank:SpareBank1:Checking",
            dedup_window_days=7,
        ),
        flag="!",
        debug=True,
    )

    assert importer.account_name == "Assets:Bank:SpareBank1:Checking"
    assert importer.flag == "!"
    assert importer.debug is True
    assert importer.dedup_window.days == 7


def test_canonical_statement_api():
    assert ModuleStatementConfig is StatementConfig

    importer = StatementImporter(
        StatementConfig(
            account_name="Assets:Bank:SpareBank1:Checking",
            dedup_window_days=7,
        ),
        flag="!",
        debug=True,
    )

    assert importer.account_name == "Assets:Bank:SpareBank1:Checking"
    assert importer.flag == "!"
    assert importer.debug is True
    assert importer.dedup_window.days == 7


def test_deprecated_deposit_aliases_warn():
    with pytest.warns(DeprecationWarning, match="Sparebank1AccountConfig is deprecated"):
        config = Sparebank1AccountConfig(
            primary_account_number="12345678901",
            account_name="Assets:Bank:SpareBank1:Checking",
        )

    with pytest.warns(DeprecationWarning, match="DepositAccountImporter is deprecated"):
        importer = DepositAccountImporter(config, flag="!", debug=True)

    assert isinstance(importer, Importer)
    assert importer.flag == "!"
    assert importer.debug is True


def test_deprecated_statement_aliases_warn():
    with pytest.warns(DeprecationWarning, match="PDFStatementConfig is deprecated"):
        config = PDFStatementConfig(account_name="Assets:Bank:SpareBank1:Checking")

    with pytest.warns(DeprecationWarning, match="PDFStatementImporter is deprecated"):
        importer = PDFStatementImporter(config, flag="!", debug=True)

    assert isinstance(importer, StatementImporter)
    assert importer.flag == "!"
    assert importer.debug is True
