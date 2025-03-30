import datetime
import re
import logging
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import pypdf
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.number import D
from beangulp import extract, similar, utils
from beangulp.importer import Importer


class PDFStatementImporter(Importer):
    """
    Importer for SpareBank 1 PDF bank statements.
    This importer processes PDF statements from SpareBank 1 in Norway,
    extracting the statement's end date and balance to create
    exactly one balance assertion per statement. The balance date
    is set to the day after the statement end date, as Beancount
    checks balances at the beginning of the specified day.
    """

    def __init__(
        self,
        account_name: str,
        currency: str = "NOK",
        prefix: str = "bank",
        dedup_window_days: int = 3,
        dedup_max_date_delta: int = 2,
        dedup_epsilon: Decimal = Decimal("0.05"),
        flag: str = "*",
    ):
        """
        Initialize a PDF statement importer.

        Args:
            account_name: The Beancount account name (e.g., "Assets:Bank:SpareBank1").
            currency: The currency of the account (default: "NOK").
            prefix: Prefix for generated filenames (default: "bank").
            flag: Transaction flag (default: "*").
            dedup_window_days: Days to look back for duplicates.
            dedup_max_date_delta: Max days difference for duplicate detection.
            dedup_epsilon: Tolerance for amount differences in duplicates.
        """
        self.account_name = account_name
        self.currency = currency
        self.prefix = prefix
        self.flag = flag

        self.dedup_window = datetime.timedelta(days=dedup_window_days)
        self.dedup_max_date_delta = datetime.timedelta(days=dedup_max_date_delta)
        self.dedup_epsilon = dedup_epsilon
        self.logger = logging.getLogger("PDFStatementImporter")

    def identify(self, filepath: str) -> bool:
        """
        Identify if the file is a Norwegian bank PDF statement.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if the file is a matching PDF, False otherwise.
        """
        path = Path(filepath)
        if not utils.is_mimetype(path, "application/pdf"):
            return False

        # Check for Norwegian bank statement indicators
        norwegian_patterns = [
            r"Kontoutskrift",
            r"Saldo.*favør",
            r"perioden\s+\d{2}\.\d{2}\.\d{4}\s+-\s+\d{2}\.\d{2}\.\d{4}",
        ]

        try:
            with path.open("rb") as f:
                pdf = pypdf.PdfReader(f)
                return len(pdf.pages) > 0 and any(
                    re.search(pattern, pdf.pages[0].extract_text())
                    for pattern in norwegian_patterns
                )
        except Exception as e:
            self.logger.debug(f"Error identifying file {filepath}: {str(e)}")
            return False

    def filename(self, filepath: str) -> str:
        """
        Generate a descriptive filename.

        Args:
            filepath: Original file path.

        Returns:
            A string with prefix and original filename.
        """
        return f"{self.prefix}.{Path(filepath).name}"

    def account(self, filepath: str) -> str:
        """Return the account name for this importer."""
        return self.account_name

    def extract(self, filepath: str, existing_entries=None) -> List[data.Directive]:
        """
        Extract a single balance assertion from a PDF statement.

        This method ensures that only one balance directive is created per file.
        The balance date is set to the day after the statement end date,
        as Beancount checks balances at the beginning of the specified day.

        Args:
            filepath: Path to the PDF file.
            existing_entries: Existing entries for deduplication.

        Returns:
            List containing exactly one balance directive.
        """
        entries = []

        try:
            # Extract text from the full PDF
            with open(filepath, "rb") as f:
                pdf = pypdf.PdfReader(f)
                if len(pdf.pages) == 0:
                    return entries

                # Get text from all pages to ensure we find the final balance
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"

                # Extract end date (last date if multiple found)
                end_date = self._extract_end_date(full_text)

                # Extract balance (last balance if multiple found)
                balance = self._extract_final_balance(full_text)

                if end_date and balance:
                    # Set balance date to the day AFTER the statement end date
                    balance_date = end_date + datetime.timedelta(days=1)

                    self.logger.info(
                        f"Found balance {balance} {self.currency} as of {end_date}"
                    )
                    self.logger.info(
                        f"Setting balance assertion date to {balance_date}"
                    )

                    # Create exactly one balance directive
                    meta = data.new_metadata(filepath, 1)

                    amount = Amount(D(balance), self.currency)

                    entry = data.Balance(
                        meta=meta,
                        date=balance_date,  # Next day after statement end date
                        account=self.account_name,
                        amount=amount,
                        tolerance=None,
                        diff_amount=None,
                    )

                    entries.append(entry)
                    self.logger.info(
                        f"Created 1 balance assertion for {self.account_name}"
                    )
                else:
                    if not end_date:
                        self.logger.warning(
                            f"Could not extract end date from {filepath}"
                        )
                    if not balance:
                        self.logger.warning(
                            f"Could not extract balance from {filepath}"
                        )

            # Mark duplicates if we have existing entries
            if existing_entries and entries:
                self.deduplicate(entries, existing_entries)

            return entries
        except Exception as e:
            self.logger.error(f"Error extracting data from {filepath}: {str(e)}")
            return entries

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

    def _extract_end_date(self, text: str) -> Optional[datetime.date]:
        """
        Extract the end date from the statement period, selecting the latest one if multiple.

        Args:
            text: Extracted text from PDF.

        Returns:
            The latest end date as a datetime.date object or None if not found.
        """
        # Find all period matches
        period_matches = re.finditer(
            r"perioden\s+\d{2}\.\d{2}\.\d{4}\s+-\s+(\d{2}\.\d{2}\.\d{4})", text
        )

        latest_date = None

        for match in period_matches:
            date_str = match.group(1)
            try:
                # Parse Norwegian date format (DD.MM.YYYY)
                day, month, year = map(int, date_str.split("."))
                current_date = datetime.date(year, month, day)

                if latest_date is None or current_date > latest_date:
                    latest_date = current_date
            except Exception as e:
                self.logger.debug(f"Error parsing date '{date_str}': {str(e)}")

        return latest_date

    def _extract_final_balance(self, text: str) -> Optional[str]:
        """
        Extract the final balance from the statement.

        Args:
            text: Extracted text from PDF.

        Returns:
            The final balance as a string or None if not found.
        """
        # Try different balance patterns
        balance_patterns = [
            r"SaldoiDeresfavør\s*([\d.,]+)",
            r"Saldo\s+i\s+Deres\s+favør\s*([\d.,]+)",
            r"Saldo.*?(\d[\d.,]+)",
            r"Saldo\s+kr\s*([\d.,]+)",
        ]

        # Find all balance matches
        all_balances = []

        for pattern in balance_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                # Handle Norwegian number format (replace comma with period)
                balance = match.group(1).replace(".", "").replace(",", ".")
                all_balances.append(balance)

        # Return the last balance found (most likely the final balance)
        if all_balances:
            return all_balances[-1]

        return None
