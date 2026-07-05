import csv
import datetime
import itertools
import warnings
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from beancount.core import data
from beancount_classifier import (
    IMPORT_FINGERPRINT_META_KEY,
    ClassifierMixin,
    ImportFingerprintTracker,
    TransactionPattern,
    counterparty,
    entry_import_fingerprint,
)
from beangulp import extract, similar, utils
from beangulp.importers.csvbase import Column, CreditOrDebit, Date
from beangulp.importers.csvbase import Importer as CSVImporter

DIALECT_NAME = "sparebank1"

csv.register_dialect(DIALECT_NAME, delimiter=";")

@dataclass
class Config:
    """Configuration for a SpareBank 1 account.

    Attributes:
        primary_account_number: The bank account number for identification.
        account_name: The Beancount account name (e.g., "Assets:Bank:SpareBank1:Checking").
        currency: The currency of the account (default: "NOK").
        other_account_mappings: List of (bank_account_number, beancount_account) tuples
            for matching counterparty bank accounts.
        transaction_patterns: List of TransactionPattern objects for narration-based
            matching using the classifier system from beancount-classifier.
        default_account: Account for unmatched transactions in either direction.
            Shorthand when one fallback is enough; leave all defaults unset to
            keep unmatched transactions without a balancing posting.
        default_expense_account: Default account for unmatched expenses
            (amount < 0). Takes precedence over default_account for expenses.
        default_income_account: Default account for unmatched income
            (amount > 0). Takes precedence over default_account for income.
        default_split_percentage: When set (0-100), matched transactions are split between
            the matched account(s) and default_account. Requires default_account to be set.
        skip_deduplication: When True, skip import_fingerprint-based deduplication.
        dedup_window_days: Days to look back for duplicates.
        dedup_max_date_delta: Max days difference for duplicate detection.
        dedup_epsilon: Tolerance for amount differences in duplicates.
    """

    primary_account_number: str
    account_name: str
    currency: str = "NOK"
    other_account_mappings: List[Tuple[str, str]] = field(default_factory=list)
    transaction_patterns: List[TransactionPattern] = field(default_factory=list)
    default_account: Optional[str] = None
    default_expense_account: Optional[str] = None
    default_income_account: Optional[str] = None
    default_split_percentage: int | float | None = None
    skip_deduplication: bool = False
    dedup_window_days: int = 3
    dedup_max_date_delta: int = 2
    dedup_epsilon: Decimal = Decimal("0.05")


Sparebank1Config = Config


@dataclass
class Sparebank1AccountConfig(Config):
    """Deprecated alias for Config."""

    def __post_init__(self) -> None:
        warnings.warn(
            "Sparebank1AccountConfig is deprecated; use Config or Sparebank1Config instead.",
            DeprecationWarning,
            stacklevel=2,
        )


class Importer(ClassifierMixin, CSVImporter):
    """
    Importer for SpareBank 1 deposit account CSV statements.

    This importer processes CSV statements from SpareBank 1 in Norway, handling
    Norwegian date and decimal formats, and categorizing transactions based on
    narration patterns.

    Uses ClassifierMixin for transaction categorization with:
    - Pattern-based matching (narration, amount, fields)
    - Counterparty matching (bank account numbers)
    - Direction-aware defaults (separate income/expense accounts)
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
    transaction_patterns: List[TransactionPattern]  # Used by ClassifierMixin
    default_account: Optional[str]  # Used by ClassifierMixin (both directions)
    default_expense: Optional[str]  # Used by ClassifierMixin (direction-aware)
    default_income: Optional[str]   # Used by ClassifierMixin (direction-aware)
    default_split_percentage: Optional[Decimal]  # Used by ClassifierMixin
    skip_deduplication: bool
    dedup_window: datetime.timedelta
    dedup_max_date_delta: datetime.timedelta
    dedup_epsilon: Decimal

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
        config: Config,
        flag: str = "*",
        debug: bool = False,
    ):
        """
        Initialize a SpareBank 1 importer using a configuration object.

        Args:
            config: A Config object with account details.
            flag: Transaction flag (default: "*").
            debug: Enable debug output (default: False).
        """
        # Store configuration values using attribute access
        self.primary_account_number = config.primary_account_number
        account_name = config.account_name  # Local var for super init
        self.currency = config.currency

        # Build transaction patterns: counterparty mappings + user patterns
        # Counterparty patterns come first (highest priority for known accounts)
        counterparty_patterns = [
            counterparty(acct_num) >> beancount_acct
            for acct_num, beancount_acct in config.other_account_mappings
        ]
        self.transaction_patterns = counterparty_patterns + list(config.transaction_patterns)

        # ClassifierMixin uses these for direction-aware defaults, falling
        # back to default_account for either direction when unset
        self.default_account = config.default_account
        self.default_expense = config.default_expense_account
        self.default_income = config.default_income_account
        self.default_split_percentage = (
            Decimal(str(config.default_split_percentage))
            if config.default_split_percentage is not None
            else None
        )

        # Store deduplication settings
        self.skip_deduplication = config.skip_deduplication
        self.dedup_window = datetime.timedelta(days=config.dedup_window_days)
        self.dedup_max_date_delta = datetime.timedelta(days=config.dedup_max_date_delta)
        self.dedup_epsilon = config.dedup_epsilon
        self.debug = debug

        self._fingerprint_tracker = ImportFingerprintTracker()

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
        """Generate a provider/account/original filename for archived data."""
        account_part = self.account_name.split(":")[-1]
        original_filename = Path(filepath).name
        return f"sparebank1.{account_part}.{original_filename}"

    def deduplicate(
        self, entries: List[data.Directive], existing: List[data.Directive]
    ) -> None:
        """
        Mark duplicate entries based on configurable parameters.

        Args:
            entries: List of new entries to check for duplicates.
            existing: List of existing entries to compare against.
        """
        if self.skip_deduplication:
            return

        heuristic_comparator = similar.heuristic_comparator(
            max_date_delta=self.dedup_max_date_delta,
            epsilon=self.dedup_epsilon,
        )

        def comparator(entry: data.Directive, target: data.Directive) -> bool:
            entry_fingerprint = entry_import_fingerprint(entry)
            target_fingerprint = entry_import_fingerprint(target)
            if entry_fingerprint and target_fingerprint:
                return entry_fingerprint == target_fingerprint
            return heuristic_comparator(entry, target)

        extract.mark_duplicate_entries(entries, existing, self.dedup_window, comparator)

    def extract(
        self, filepath: str, existing: List[data.Directive]
    ) -> List[data.Directive]:
        """Extract entries, resetting fingerprint state for the file."""
        self._fingerprint_tracker.reset()
        return super().extract(filepath, existing)

    def _fingerprint_parts(self, row: Any) -> tuple[str, ...]:
        """Row-content identity parts for SpareBank 1 CSV imports."""
        return (
            str(getattr(row, "date", "")),
            str(getattr(row, "amount", "")),
            getattr(row, "narration", "") or "",
            getattr(row, "rentedato", "") or "",
            getattr(row, "til_konto", "") or "",
            getattr(row, "fra_konto", "") or "",
        )

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
        meta[IMPORT_FINGERPRINT_META_KEY] = self._fingerprint_tracker.fingerprint(
            self._fingerprint_parts(row)
        )

        # Filter out None values to keep metadata clean
        return {k: v for k, v in meta.items() if v != ""}

    def get_fields(self, row: Any) -> Dict[str, str] | None:
        """
        Extract fields from the CSV row for pattern matching.

        Used by ClassifierMixin for field-based and counterparty matching.

        Args:
            row: The row object from the CSV.

        Returns:
            Dictionary with from_account and to_account fields.
        """
        fields = {}
        from_account = getattr(row, "fra_konto", "")
        to_account = getattr(row, "til_konto", "")

        if from_account:
            fields["from_account"] = from_account
        if to_account:
            fields["to_account"] = to_account

        return fields if fields else None


class DepositAccountImporter(Importer):
    """Deprecated alias for Importer."""

    def __init__(
        self,
        config: Config,
        flag: str = "*",
        debug: bool = False,
    ):
        warnings.warn(
            "DepositAccountImporter is deprecated; use Importer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(config, flag=flag, debug=debug)
