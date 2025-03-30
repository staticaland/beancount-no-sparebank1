import csv
import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from beancount.core import data
from beancount.core.amount import Amount
from beangulp import extract, similar, utils
from beangulp.importers.csvbase import Column, CreditOrDebit, Date, Importer
from beangulp.testing import main as test_main


DIALECT_NAME = "sparebank1"

csv.register_dialect(DIALECT_NAME, delimiter=";")


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

    def account(self, filepath: str) -> str:
        """
        Determine the account based on the first transaction in the CSV file.

        Args:
            filepath: Path to the CSV file.

        Returns:
            The Beancount account name for this CSV file.
        """
        with open(filepath, "r", encoding=self.encoding) as f:
            reader = csv.DictReader(f, dialect=self.dialect)
            first_row = next(reader, None)

            if not first_row:
                return self.importer_account

            # Check if it's an incoming transaction (if Inn is not empty)
            inn_amount = first_row.get("Inn", "").strip()

            # Get our account number based on direction
            if inn_amount:  # Incoming transaction
                account_number = first_row.get("Fra konto", "").strip()
            else:  # Outgoing transaction
                account_number = first_row.get("Til konto", "").strip()

            # Look up account in mappings
            for pattern, account in self.account_number_to_account_mappings:
                if pattern == account_number:
                    return account

            # If no mapping found, return the default account
            return self.importer_account

    def __init__(
        self,
        account_name: str,
        currency: str = "NOK",
        narration_to_account_mappings: Optional[Sequence[Tuple[str, str]]] = None,
        account_number_to_account_mappings: Optional[Sequence[Tuple[str, str]]] = None,
        default_expense_account: str = "Expenses:Uncategorized",
        default_income_account: str = "Income:Uncategorized",
        dedup_window_days: int = 3,
        dedup_max_date_delta: int = 2,
        dedup_epsilon: Decimal = Decimal("0.05"),
        flag: str = "*",
    ):
        """
        Initialize a SpareBank 1 importer.

        Args:
            account_name: The Beancount account name (e.g., "Assets:Bank:SpareBank1").
            currency: The currency of the account (default: "NOK").
            narration_to_account_mappings: Optional list of (pattern, account) tuples
                to map narration patterns to accounts for categorization.
            account_number_to_account_mappings: Optional list of (account_number, account) tuples
                to map account numbers to Beancount accounts for categorization.
            default_expense_account: Default account to use for outgoing transactions when no mapping matches.
            default_income_account: Default account to use for incoming transactions when no mapping matches.
            flag: Transaction flag (default: "*").
            dedup_window_days: Days to look back for duplicates.
            dedup_max_date_delta: Max days difference for duplicate detection.
            dedup_epsilon: Tolerance for amount differences in duplicates.
        """

        self.narration_to_account_mappings = narration_to_account_mappings or []
        self.account_number_to_account_mappings = (
            account_number_to_account_mappings or []
        )
        self.default_expense_account = default_expense_account
        self.default_income_account = default_income_account
        self.dedup_window = datetime.timedelta(days=dedup_window_days)
        self.dedup_max_date_delta = datetime.timedelta(days=dedup_max_date_delta)
        self.dedup_epsilon = dedup_epsilon
        super().__init__(account_name, currency, flag=flag)

    def identify(self, filepath: str) -> bool:
        """
        Identify if the file is a SpareBank 1 CSV statement.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if the file is a matching CSV, False otherwise.
        """

        if not utils.is_mimetype(filepath, "text/csv"):
            return False
        return utils.search_file_regexp(
            filepath,
            "Dato;Beskrivelse;Rentedato;Inn;Ut;Til konto;Fra konto",
            encoding=self.encoding,
        )

    def filename(self, filepath: str) -> str:
        """
        Generate a descriptive filename.

        Args:
            filepath: Original file path.

        Returns:
            A string with account name and original filename.
        """
        return f"sparebank1.{Path(filepath).name}"

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
        and narration patterns.

        Mapping precedence:
        1. Account number mappings (direction-aware):
        - For outgoing transactions: check til_konto (destination)
        - For incoming transactions: check fra_konto (source)
        2. Narration patterns
        3. Default accounts based on transaction direction

        Args:
            txn: The transaction object to finalize.
            row: The row object from the CSV.

        Returns:
            The modified transaction, or None if invalid.
        """
        if not txn.postings:
            return txn

        amount = txn.postings[0].units.number
        from_account = getattr(row, "fra_konto", "")
        to_account = getattr(row, "til_konto", "")

        # Check account number mappings first
        if amount < 0 and to_account:  # Outgoing
            for pattern, account in self.account_number_to_account_mappings:
                if pattern == to_account:
                    opposite_units = Amount(-amount, self.currency)
                    balancing_posting = data.Posting(
                        account=account,
                        units=opposite_units,
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None,
                    )
                    return txn._replace(postings=txn.postings + [balancing_posting])
        elif amount > 0 and from_account:  # Incoming
            for pattern, account in self.account_number_to_account_mappings:
                if pattern == from_account:
                    opposite_units = Amount(-amount, self.currency)
                    balancing_posting = data.Posting(
                        account=account,
                        units=opposite_units,
                        cost=None,
                        price=None,
                        flag=None,
                        meta=None,
                    )
                    return txn._replace(postings=txn.postings + [balancing_posting])

        # Then check narration patterns
        for pattern, account in self.narration_to_account_mappings:
            if pattern in txn.narration:
                opposite_units = Amount(-amount, self.currency)
                balancing_posting = data.Posting(
                    account=account,
                    units=opposite_units,
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None,
                )
                return txn._replace(postings=txn.postings + [balancing_posting])

        # Finally, use default accounts
        default_account = (
            self.default_income_account if amount > 0 else self.default_expense_account
        )
        opposite_units = Amount(-amount, self.currency)
        balancing_posting = data.Posting(
            account=default_account,
            units=opposite_units,
            cost=None,
            price=None,
            flag=None,
            meta=None,
        )
        return txn._replace(postings=txn.postings + [balancing_posting])


def main():
    test_main(
        DepositAccountImporter(
            account_number_to_account_mappings=[
                ("12345678901", "Assets:Bank:SpareBank1:Checking"),
                ("98712345678", "Assets:Bank:SpareBank1:Savings"),
                ("56712345678", "Income:Salary"),
            ],
            narration_to_account_mappings=[
                ("KIWI", "Expenses:Groceries"),
                ("MENY", "Expenses:Groceries"),
                ("VINMONOPOLET", "Expenses:Alcohol"),
            ],
            default_expense_account="Expenses:Uncategorized",
            default_income_account="Income:Uncategorized",
        )
    )


if __name__ == "__main__":
    main()
