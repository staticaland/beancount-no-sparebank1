import csv
import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import itertools
from dataclasses import dataclass, field

from beancount.core import data
from beancount.core.amount import Amount
from beangulp import extract, similar, utils
from beangulp.importers.csvbase import Column, CreditOrDebit, Date, Importer
from beangulp.testing import main as test_main

from beancount_classifier import (
    TransactionPattern,
    TransactionClassifier,
    amount,
    match,
    when,
    field,
)


DIALECT_NAME = "sparebank1"

csv.register_dialect(DIALECT_NAME, delimiter=";")


@dataclass
class Sparebank1AccountConfig:
    """Configuration for a SpareBank 1 account.

    Attributes:
        primary_account_number: The bank account number for identification.
        account_name: The Beancount account name (e.g., "Assets:Bank:SpareBank1:Checking").
        currency: The currency of the account (default: "NOK").
        other_account_mappings: List of (bank_account_number, beancount_account) tuples
            for matching counterparty bank accounts.
        transaction_patterns: List of TransactionPattern objects for narration-based
            matching using the classifier system from beancount-no-amex.
        default_expense_account: Default account for unmatched expenses.
        default_income_account: Default account for unmatched income.
    """

    primary_account_number: str
    account_name: str
    currency: str
    other_account_mappings: List[Tuple[str, str]] = field(default_factory=list)
    transaction_patterns: List[TransactionPattern] = field(default_factory=list)
    default_expense_account: str = "Expenses:Unknown"
    default_income_account: str = "Income:Unknown"


class DepositAccountImporter(Importer):
    """
    Importer for SpareBank 1 deposit account CSV statements.

    This importer processes CSV statements from SpareBank 1 in Norway, handling
    Norwegian date and decimal formats, and categorizing transactions based on
    narration patterns.
    """

    # Configure csvbase options
    dialect = DIALECT_NAME
    encoding = "utf-8-sig"  # Handle BOM if present

    # CSV file has a header line
    names = True

    # Configure column mappings
    date = Date("Dato", "%d.%m.%Y")  # Norwegian date format
    narration = Column("Beskrivelse")

    amount = CreditOrDebit(
        subs={
            ",": ".",  # Convert decimal separator
            "-": "",  # Remove negative signs
        },
        credit="Inn",  # Values in this column are KEPT AS-IS
        debit="Ut",  # Values in this column are NEGATED
    )

    # Map the metadata fields
    rentedato = Column("Rentedato")
    til_konto = Column("Til konto")
    fra_konto = Column("Fra konto")

    # Instance attributes to be populated from config
    primary_account_number: str
    account_name: str
    currency: str
    other_account_mappings: List[Tuple[str, str]]
    transaction_patterns: List[TransactionPattern]
    default_expense_account: str
    default_income_account: str
    dedup_window: datetime.timedelta
    dedup_max_date_delta: datetime.timedelta
    dedup_epsilon: Decimal
    _classifier: TransactionClassifier

    def account(self, filepath: str) -> str:
        """
        Return the configured account name for this importer instance.

        Args:
            filepath: Path to the CSV file (unused, but required by base class).

        Returns:
            The Beancount account name associated with this importer configuration.
        """
        return self.account_name

    def __init__(
        self,
        config: Sparebank1AccountConfig,
        dedup_window_days: int = 3,
        dedup_max_date_delta: int = 2,
        dedup_epsilon: Decimal = Decimal("0.05"),
        flag: str = "*",
    ):
        """
        Initialize a SpareBank 1 importer using a configuration object.

        Args:
            config: A Sparebank1AccountConfig object with account details.
            flag: Transaction flag (default: "*").
            dedup_window_days: Days to look back for duplicates.
            dedup_max_date_delta: Max days difference for duplicate detection.
            dedup_epsilon: Tolerance for amount differences in duplicates.
        """
        # Store configuration values using attribute access
        self.primary_account_number = config.primary_account_number
        account_name = config.account_name  # Local var for super init
        self.currency = config.currency
        self.other_account_mappings = config.other_account_mappings
        self.transaction_patterns = config.transaction_patterns
        self.default_expense_account = config.default_expense_account
        self.default_income_account = config.default_income_account

        # Create the transaction classifier for narration-based matching
        self._classifier = TransactionClassifier(
            patterns=self.transaction_patterns,
            default_account=None,  # We handle defaults separately based on direction
        )

        # Store deduplication settings
        self.dedup_window = datetime.timedelta(days=dedup_window_days)
        self.dedup_max_date_delta = datetime.timedelta(days=dedup_max_date_delta)
        self.dedup_epsilon = dedup_epsilon

        # Call parent constructor AFTER storing config needed by other methods
        super().__init__(account_name, self.currency, flag=flag)
        # Now store account_name on self as well, consistent with other attrs
        self.account_name = account_name

    def identify(self, filepath: str) -> bool:
        """
        Identify if the file is a SpareBank 1 CSV statement *and* belongs
        to the primary account number configured for this importer.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if the file is a matching CSV for this specific account, False otherwise.
        """
        # Basic checks: mimetype and header
        if not utils.is_mimetype(filepath, "text/csv"):
            return False
        if not utils.search_file_regexp(
            filepath,
            "Dato;Beskrivelse;Rentedato;Inn;Ut;Til konto;Fra konto",
            encoding=self.encoding,
        ):
            return False

        # Advanced check: verify if transactions involve the primary account number
        try:
            with open(filepath, "r", encoding=self.encoding) as f:
                reader = csv.DictReader(f, dialect=self.dialect)
                # Check the first few rows to see if our account number appears
                # It seems 'Fra konto' is the source, 'Til konto' is the destination.
                # For an outgoing transaction ('Ut' has value), 'Fra konto' is *our* account.
                # For an incoming transaction ('Inn' has value), 'Til konto' is *our* account.
                for row in itertools.islice(
                    reader, 10
                ):  # Check only first 10 rows for efficiency
                    from_account = row.get("Fra konto", "").strip()
                    to_account = row.get("Til konto", "").strip()
                    is_outgoing = bool(
                        row.get("Ut", "").strip()
                    )  # Check if 'Ut' has content

                    our_account_in_row = from_account if is_outgoing else to_account

                    if our_account_in_row == self.primary_account_number:
                        # Found a transaction linked to our primary account. Assume file is correct.
                        return True

                # If we checked rows and didn't find our account, it's likely not the right file.
                # Or the file might be empty/only have header, which find_file_account handles.
                return False
        except (FileNotFoundError, csv.Error, Exception):
            # Handle potential errors during file reading or CSV parsing
            # Consider logging this instead of printing: import logging; logging.exception(...)
            return False  # If we can't read/parse, we can't identify

    def filename(self, filepath: str) -> str:
        """
        Generate a descriptive filename using the configured account name.

        Args:
            filepath: Original file path.

        Returns:
            A string with a sanitized account name and original filename.
        """
        # Sanitize account name for use in filename
        # Use self.account_name which is set in __init__
        account_part = self.account_name.replace(":", "-").replace(" ", "_")
        original_filename = Path(filepath).name
        return f"{account_part}.{original_filename}"

    def deduplicate(
        self, entries: List[data.Directive], existing: List[data.Directive]
    ) -> None:
        """
        Mark duplicate entries based on configurable parameters.

        Args:
            entries: List of new entries to check for duplicates.
            existing: List of existing entries to compare against.
        """

        comparator = similar.heuristic_comparator(
            max_date_delta=self.dedup_max_date_delta,
            epsilon=self.dedup_epsilon,
        )

        extract.mark_duplicate_entries(entries, existing, self.dedup_window, comparator)

    def metadata(self, filepath: str, lineno: int, row: Any) -> Dict[str, Any]:
        """
        Build transaction metadata dictionary from row data.

        Args:
            filepath: Path to the CSV file.
            lineno: Line number in the file.
            row: Row object containing parsed CSV data.

        Returns:
            Dictionary of metadata key-value pairs.
        """

        meta = super().metadata(filepath, lineno, row)

        meta["rentedato"] = getattr(row, "rentedato", "")
        meta["to_account"] = getattr(row, "til_konto", "")
        meta["from_account"] = getattr(row, "fra_konto", "")

        # Filter out None values to keep metadata clean
        return {k: v for k, v in meta.items() if v != ""}

    def finalize(self, txn: data.Transaction, row: Any) -> Optional[data.Transaction]:
        """
        Post-process the transaction with categorization based on account numbers
        and narration patterns using the classifier system.

        Mapping precedence:
        1. Account number mappings (direction-aware)
        2. TransactionPattern matching via classifier (narration/amount based)
        3. Default accounts based on transaction direction

        Args:
            txn: The transaction object to finalize.
            row: The row object from the CSV.

        Returns:
            The modified transaction, or None if invalid.
        """
        if not txn.postings:
            return txn

        txn_amount = txn.postings[0].units.number
        from_account = getattr(row, "fra_konto", "")
        to_account = getattr(row, "til_konto", "")
        narration = txn.narration or ""

        # 1. Check account number mappings (direction-aware)
        # Determine which account number to check based on transaction direction
        account_to_check = to_account if txn_amount < 0 else from_account
        if account_to_check:
            for pattern, acc in self.other_account_mappings:
                if pattern == account_to_check:
                    # Found a match via bank account number
                    balancing_posting = data.Posting(
                        account=acc,
                        units=Amount(-txn_amount, self.currency),
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None,
                    )
                    return txn._replace(postings=txn.postings + [balancing_posting])

        # 2. Use the classifier for narration/amount/field-based pattern matching
        # Build fields dict for field-based pattern matching
        fields = {}
        if from_account:
            fields["from_account"] = from_account
        if to_account:
            fields["to_account"] = to_account

        if result := self._classifier.classify(narration, txn_amount, fields if fields else None):
            return self._classifier.add_balancing_postings(txn, result)

        # 3. Use default accounts if no specific rule matched
        default_account = (
            self.default_income_account
            if txn_amount > 0
            else self.default_expense_account
        )

        balancing_posting = data.Posting(
            account=default_account,
            units=Amount(-txn_amount, self.currency),
            cost=None,
            price=None,
            flag=None,
            meta=None,
        )
        return txn._replace(postings=txn.postings + [balancing_posting])


def main():
    checking_config = Sparebank1AccountConfig(
        primary_account_number="12345678901",
        account_name="Assets:Bank:SpareBank1:Checking",
        currency="NOK",
        other_account_mappings=[
            ("98712345678", "Assets:Bank:SpareBank1:Savings"),
            ("56712345678", "Income:Salary"),
        ],
        transaction_patterns=[
            # Fluent API - simple substring matching
            match("KIWI") >> "Expenses:Groceries",
            match("MENY") >> "Expenses:Groceries",
            match("VINMONOPOLET") >> "Expenses:Alcohol",
            match("RUTER") >> "Expenses:Transport",

            # Fluent API - regex matching
            match(r"REMA\s*1000").regex >> "Expenses:Groceries",

            # Fluent API - case-insensitive
            match("spotify").ignorecase >> "Expenses:Subscriptions",

            # Fluent API - amount condition with narration
            match("ATM").where(amount > 500) >> "Expenses:Cash:Large",

            # Fluent API - amount-only matching
            when(amount < 50) >> "Expenses:PettyCash",

            # Fluent API - field-based matching (matches bank account numbers)
            field(to_account="11112222333") >> "Assets:Bank:SpareBank1:Savings",
        ],
        # Default values are handled by the dataclass, but can be overridden if needed
        # default_expense_account="Expenses:SomethingElse",
        # default_income_account="Income:SomethingElse",
    )

    checking_importer = DepositAccountImporter(config=checking_config)

    test_main(checking_importer)


if __name__ == "__main__":
    main()
