import datetime

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.number import D

from beancount_no_sparebank1 import StatementConfig, StatementImporter
from beancount_no_sparebank1.balance import same_balance_assertion


def balance(account: str, date: datetime.date, amount: str = "100.00") -> data.Balance:
    return data.Balance(
        meta=data.new_metadata("<test>", 1),
        date=date,
        account=account,
        amount=Amount(D(amount), "NOK"),
        tolerance=None,
        diff_amount=None,
    )


def test_pdf_statement_config_controls_balance_assertions() -> None:
    importer = StatementImporter(
        StatementConfig(
            account_name="Assets:Bank:SpareBank1:Checking",
            generate_balance_assertions=False,
        )
    )

    assert importer.account_name == "Assets:Bank:SpareBank1:Checking"
    assert importer.generate_balance_assertions is False
    assert importer.extract("missing.pdf", []) == []


def test_pdf_statement_importer_uses_config_dedup_tuning() -> None:
    importer = StatementImporter(
        StatementConfig(
            account_name="Assets:Bank:SpareBank1:Checking",
            dedup_window_days=7,
            dedup_max_date_delta=4,
            dedup_epsilon=D("0.10"),
        )
    )

    assert importer.account_name == "Assets:Bank:SpareBank1:Checking"
    assert importer.dedup_window.days == 7
    assert importer.dedup_max_date_delta.days == 4
    assert importer.dedup_epsilon == D("0.10")


def test_pdf_statement_filename_uses_provider_and_account_leaf(tmp_path) -> None:
    importer = StatementImporter(
        StatementConfig(
            account_name="Assets:Bank:SpareBank1:Checking",
            prefix="legacy",
        )
    )
    statement = tmp_path / "statement.pdf"

    assert importer.filename(str(statement)) == "sparebank1.Checking.statement.pdf"


def test_pdf_statement_identify_accepts_renamed_pdf_content(tmp_path, monkeypatch) -> None:
    class FakePage:
        def extract_text(self):
            return "Kontoutskrift for perioden 01.01.2025 - 31.01.2025"

    class FakeReader:
        def __init__(self, _file):
            self.pages = [FakePage()]

    monkeypatch.setattr("beancount_no_sparebank1.balance.pypdf.PdfReader", FakeReader)
    importer = StatementImporter(
        StatementConfig(account_name="Assets:Bank:SpareBank1:Checking")
    )
    statement = tmp_path / "renamed.txt"
    statement.write_bytes(b"%PDF-1.7")

    assert importer.identify(str(statement)) is True


def test_balance_assertion_duplicates_match_on_account_and_date() -> None:
    first = balance("Assets:Bank:SpareBank1:Checking", datetime.date(2025, 2, 1), "10.00")
    same_identity = balance("Assets:Bank:SpareBank1:Checking", datetime.date(2025, 2, 1), "20.00")
    different_date = balance("Assets:Bank:SpareBank1:Checking", datetime.date(2025, 2, 2), "10.00")
    different_account = balance("Assets:Bank:SpareBank1:Savings", datetime.date(2025, 2, 1), "10.00")

    assert same_balance_assertion(first, same_identity)
    assert not same_balance_assertion(first, different_date)
    assert not same_balance_assertion(first, different_account)
