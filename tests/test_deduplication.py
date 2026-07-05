import datetime

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.number import D

from beancount_no_sparebank1.deposit import (
    DepositAccountImporter,
    Sparebank1AccountConfig,
)


def _importer() -> DepositAccountImporter:
    config = Sparebank1AccountConfig(
        primary_account_number="12345678901",
        account_name="Assets:Bank:SpareBank1:Checking",
    )
    return DepositAccountImporter(config)


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
    entries = [_transaction("same-fingerprint")]
    existing = [_transaction("same-fingerprint")]

    _importer().deduplicate(entries, existing)

    assert "__duplicate__" in entries[0].meta


def test_different_fingerprints_prevent_fuzzy_false_positive() -> None:
    entries = [_transaction("new-fingerprint")]
    existing = [_transaction("existing-fingerprint")]

    _importer().deduplicate(entries, existing)

    assert "__duplicate__" not in entries[0].meta


def test_heuristic_fallback_handles_identityless_history() -> None:
    entries = [_transaction("new-fingerprint")]
    existing = [_transaction(None)]

    _importer().deduplicate(entries, existing)

    assert "__duplicate__" in entries[0].meta
