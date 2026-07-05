import datetime

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.number import D

from beancount_no_sparebank1.deposit import (
    Config,
    Importer,
)


def _importer() -> Importer:
    config = Config(
        primary_account_number="12345678901",
        account_name="Assets:Bank:SpareBank1:Checking",
    )
    return Importer(config)


def test_dedup_tuning_lives_in_config() -> None:
    importer = Importer(
        Config(
            primary_account_number="12345678901",
            account_name="Assets:Bank:SpareBank1:Checking",
            default_account="Expenses:NeedsReview",
            default_split_percentage=50,
            dedup_window_days=7,
            dedup_max_date_delta=4,
            dedup_epsilon=D("0.10"),
        )
    )

    assert importer.default_split_percentage == D("50")
    assert importer.dedup_window.days == 7
    assert importer.dedup_max_date_delta.days == 4
    assert importer.dedup_epsilon == D("0.10")


def test_csv_filename_uses_provider_and_account_leaf(tmp_path) -> None:
    statement = tmp_path / "2025-01.csv"

    assert _importer().filename(str(statement)) == "sparebank1.Checking.2025-01.csv"


def test_identify_accepts_renamed_csv_when_content_matches(tmp_path) -> None:
    statement = tmp_path / "renamed.txt"
    statement.write_text(
        "\ufeffDato;Beskrivelse;Rentedato;Inn;Ut;Til konto;Fra konto\n"
        "01.01.2025;PAY;01.01.2025;;100,00;;12345678901\n",
        encoding="utf-8",
    )

    assert _importer().identify(str(statement)) is True


def test_identify_rejects_csv_for_other_account(tmp_path) -> None:
    statement = tmp_path / "renamed.txt"
    statement.write_text(
        "\ufeffDato;Beskrivelse;Rentedato;Inn;Ut;Til konto;Fra konto\n"
        "01.01.2025;PAY;01.01.2025;;100,00;;99999999999\n",
        encoding="utf-8",
    )

    assert _importer().identify(str(statement)) is False


def _transaction(fingerprint: str | None, amount: str = "-100.00") -> data.Transaction:
    meta = data.new_metadata("<test>", 1)
    if fingerprint is not None:
        meta["import_fingerprint"] = fingerprint
    return data.Transaction(
        meta=meta,
        date=datetime.date(2025, 10, 24),
        flag="*",
        payee=None,
        narration="TEST MERCHANT",
        tags=data.EMPTY_SET,
        links=data.EMPTY_SET,
        postings=[
            data.Posting(
                "Assets:Bank:SpareBank1:Checking",
                Amount(D(amount), "NOK"),
                None,
                None,
                None,
                None,
            )
        ],
    )


def test_matching_fingerprint_marks_duplicate() -> None:
    entries: list[data.Directive] = [_transaction("same-fingerprint")]
    existing: list[data.Directive] = [_transaction("same-fingerprint")]

    _importer().deduplicate(entries, existing)

    assert "__duplicate__" in entries[0].meta


def test_skip_deduplication_leaves_matching_fingerprint_unmarked() -> None:
    entries: list[data.Directive] = [_transaction("same-fingerprint")]
    existing: list[data.Directive] = [_transaction("same-fingerprint")]
    importer = Importer(
        Config(
            primary_account_number="12345678901",
            account_name="Assets:Bank:SpareBank1:Checking",
            skip_deduplication=True,
        )
    )

    importer.deduplicate(entries, existing)

    assert "__duplicate__" not in entries[0].meta


def test_different_fingerprints_prevent_fuzzy_false_positive() -> None:
    entries: list[data.Directive] = [_transaction("new-fingerprint")]
    existing: list[data.Directive] = [_transaction("existing-fingerprint")]

    _importer().deduplicate(entries, existing)

    assert "__duplicate__" not in entries[0].meta


def test_heuristic_fallback_handles_identityless_history() -> None:
    entries: list[data.Directive] = [_transaction("new-fingerprint")]
    existing: list[data.Directive] = [_transaction(None)]

    _importer().deduplicate(entries, existing)

    assert "__duplicate__" in entries[0].meta
