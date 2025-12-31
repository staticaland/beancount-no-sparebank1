# beancount-no-sparebank1

A Python library that imports Norwegian SpareBank 1 data into Beancount accounting format.

![sb12](https://github.com/user-attachments/assets/e0e90691-1430-4bd1-a29d-e1605e30b857)

## Features

-   Import transactions from CSV exports of SpareBank 1 deposit accounts
-   Extract balance statements from PDF account statements ("kontoutskrift")
-   Fluent, human-readable classification API
-   Field-based matching on bank account numbers
-   Automatic duplicate detection

## Quickstart

### 1. Create a new project

```bash
mkdir finances && cd finances
uv init
```

### 2. Add dependencies

```bash
uv add beancount fava
uv add beangulp --git https://github.com/beancount/beangulp
uv add beancount-no-sparebank1 --git https://github.com/staticaland/beancount-no-sparebank1
```

### 3. Configure as a package

Add to your `pyproject.toml`:

```toml
[tool.uv]
package = true

[project.scripts]
import-transactions = "finances.importers:main"
```

Then sync:

```bash
uv sync
```

### 4. Create the importer

Create `src/finances/importers.py`:

```python
from beangulp import Ingest
from beancount_no_sparebank1 import (
    DepositAccountImporter,
    Sparebank1AccountConfig,
    match,
    when,
    field,
    counterparty,
    amount,
)


def get_importers():
    return [
        DepositAccountImporter(Sparebank1AccountConfig(
            primary_account_number="12345678901",
            account_name="Assets:Bank:SpareBank1:Checking",
            currency="NOK",

            # Map bank account numbers to Beancount accounts
            other_account_mappings=[
                ("98712345678", "Assets:Bank:SpareBank1:Savings"),
                ("56712345678", "Income:Salary"),
            ],

            transaction_patterns=[
                # Simple substring matching
                match("KIWI") >> "Expenses:Groceries",
                match("MENY") >> "Expenses:Groceries",
                match("VINMONOPOLET") >> "Expenses:Alcohol",
                match("RUTER") >> "Expenses:Transport",

                # Regex matching
                match(r"REMA\s*1000").regex >> "Expenses:Groceries",

                # Case-insensitive
                match("spotify").ignorecase >> "Expenses:Subscriptions",

                # Amount-based rules
                when(amount < 50) >> "Expenses:PettyCash",
                when(amount > 5000) >> "Expenses:Large",

                # Combined: narration + amount
                match("ATM").where(amount > 500) >> "Expenses:Cash:Large",

                # Field-based: match by destination account number
                field(to_account="11112222333") >> "Assets:Bank:SpareBank1:Savings",
            ],

            default_expense_account="Expenses:Unknown",
            default_income_account="Income:Unknown",
        )),
    ]


def main():
    ingest = Ingest(get_importers())
    ingest.main()


if __name__ == "__main__":
    main()
```

Also create `src/finances/__init__.py`:

```bash
mkdir -p src/finances
touch src/finances/__init__.py
```

### 5. Create the main ledger file

Create `main.beancount`:

```beancount
option "title" "My Finances"
option "operating_currency" "NOK"

2020-01-01 open Assets:Bank:SpareBank1:Checking NOK
2020-01-01 open Assets:Bank:SpareBank1:Savings NOK
2020-01-01 open Expenses:Groceries NOK
2020-01-01 open Expenses:Alcohol NOK
2020-01-01 open Expenses:Transport NOK
2020-01-01 open Expenses:Subscriptions NOK
2020-01-01 open Expenses:PettyCash NOK
2020-01-01 open Expenses:Unknown NOK
2020-01-01 open Income:Salary NOK
2020-01-01 open Income:Unknown NOK

include "imports/*.beancount"
```

Create the imports directory:

```bash
mkdir -p imports
```

### 6. Download your SpareBank 1 statement

1. Log in to SpareBank 1 nettbank
2. Go to your account and find "Kontoutskrift" or "Eksporter"
3. Download as CSV
4. Place it in a `downloads/` folder

### 7. Import transactions

```bash
# Preview what will be imported
uv run import-transactions extract downloads/

# Save to a file
uv run import-transactions extract downloads/ > imports/2024-sparebank1.beancount
```

### 8. View in Fava

```bash
uv run fava main.beancount
```

Open http://localhost:5000 in your browser.

## Classification API

The library provides a fluent, human-readable API for transaction classification, powered by [beancount-classifier](https://github.com/staticaland/beancount-classifier):

```python
from beancount_no_sparebank1 import match, when, field, counterparty, shared, amount

rules = [
    # Simple substring matching
    match("SPOTIFY") >> "Expenses:Music",
    match("NETFLIX") >> "Expenses:Entertainment",

    # Regex patterns
    match(r"REMA\s*1000").regex >> "Expenses:Groceries",

    # Case-insensitive matching
    match("starbucks").ignorecase >> "Expenses:Coffee",
    match("starbucks").i >> "Expenses:Coffee",  # short form

    # Amount-based rules
    when(amount < 50) >> "Expenses:PettyCash",
    when(amount > 1000) >> "Expenses:Large",
    when(amount.between(100, 500)) >> "Expenses:Medium",

    # Combined conditions
    match("VINMONOPOLET").where(amount > 500) >> "Expenses:Alcohol:Fine",

    # Counterparty matching (direction-aware bank account matching)
    # For expenses: matches to_account, for income: matches from_account
    counterparty("98712345678") >> "Assets:Savings",
    counterparty("56712345678") >> "Income:Salary",

    # Field-based matching (explicit field matching)
    field(to_account="98712345678") >> "Assets:Savings",
    field(from_account="56712345678") >> "Income:Salary",

    # Split across multiple accounts
    match("COSTCO") >> [
        ("Expenses:Groceries", 80),
        ("Expenses:Household", 20),
    ],

    # Shared expenses (tracking what roommates owe you)
    match("GROCERIES") >> "Expenses:Groceries" | shared("Assets:Receivables:Alex", 50),
]
```

### API Reference

| Pattern Type        | Example                                       | Description                                  |
| ------------------- | --------------------------------------------- | -------------------------------------------- |
| Substring           | `match("SPOTIFY") >> "..."`                   | Matches if narration contains "SPOTIFY"      |
| Regex               | `match(r"REMA\s*1000").regex >> "..."`        | Regex pattern matching                       |
| Case-insensitive    | `match("spotify").ignorecase >> "..."`        | Case-insensitive match                       |
| Amount less than    | `when(amount < 50) >> "..."`                  | Amount under threshold                       |
| Amount greater than | `when(amount > 500) >> "..."`                 | Amount over threshold                        |
| Amount range        | `when(amount.between(100, 500)) >> "..."`     | Amount within range                          |
| Combined            | `match("STORE").where(amount > 100) >> "..."` | Narration + amount condition                 |
| Counterparty        | `counterparty("123") >> "..."`                | Direction-aware account matching (see below) |
| Field match         | `field(to_account="123") >> "..."`            | Match on specific CSV fields                 |
| Split               | `match("X") >> [("A", 80), ("B", 20)]`        | Split across accounts                        |
| Shared              | `... >> "X" \| shared("Receivable", 50)`      | Track shared expenses                        |

### Counterparty Matching

The `counterparty()` helper provides direction-aware account matching:

-   **For expenses** (amount < 0): matches against `to_account` (where money goes)
-   **For income** (amount > 0): matches against `from_account` (where money comes from)

This simplifies mapping known bank accounts:

```python
# Instead of two separate rules:
field(to_account="98712345678").where(amount < 0) >> "Assets:Savings"
field(from_account="98712345678").where(amount > 0) >> "Assets:Savings"

# Use one counterparty rule:
counterparty("98712345678") >> "Assets:Savings"
```

### Available Fields

The SpareBank 1 importer exposes these fields for matching:

-   `to_account` - Destination bank account number (from "Til konto" column)
-   `from_account` - Source bank account number (from "Fra konto" column)

## PDF Balance Statements

Extract balance assertions from PDF "kontoutskrift" statements:

```python
from beancount_no_sparebank1 import PDFStatementImporter

importers = [
    PDFStatementImporter(
        account_name="Assets:Bank:SpareBank1:Checking",
        currency="NOK",
    ),
]
```

## Configuration Reference

```python
Sparebank1AccountConfig(
    # Required
    primary_account_number="12345678901",  # Your account number (for file matching)
    account_name="Assets:Bank:SpareBank1:Checking",
    currency="NOK",

    # Optional: map counterparty bank accounts to Beancount accounts
    other_account_mappings=[
        ("98712345678", "Assets:Bank:SpareBank1:Savings"),
    ],

    # Optional: classification patterns (fluent API or TransactionPattern)
    transaction_patterns=[
        match("KIWI") >> "Expenses:Groceries",
    ],

    # Optional: fallback accounts for unmatched transactions
    default_expense_account="Expenses:Unknown",
    default_income_account="Income:Unknown",
)
```

## Notes

-   Each CSV file should contain transactions from a single account
-   The importer identifies files by checking if the primary account number appears in transactions
-   Duplicate detection uses date, amount, and narration similarity

## See also

-   [beancount-classifier](https://github.com/staticaland/beancount-classifier) - The classification engine powering this importer
-   [beancount-no-amex](https://github.com/staticaland/beancount-no-amex) - American Express Norway importer
-   [Automatically balancing Beancount DKB transactions](https://sgoel.dev/posts/automatically-balancing-beancount-dkb-transactions/)
-   [siddhantgoel/beancount-dkb](https://github.com/siddhantgoel/beancount-dkb)
