# beancount-no-sparebank1

A Python library that imports Norwegian SpareBank 1 data into Beancount accounting format.

![sb12](https://github.com/user-attachments/assets/e0e90691-1430-4bd1-a29d-e1605e30b857)

## Features

- Import transactions from CSV exports of SpareBank 1 deposit accounts
- Extract balance statements from PDF account statements ("kontoutskrift")
- Flexible transaction categorization with customizable rules

## Notes

- It is assumed that a file never has mixed transactions.

## Quick start

There are several ways to use this library. Choose the approach that best fits your workflow:

### Option 1: Using uv with script dependencies (Recommended)

Create a Python script with inline dependency declarations. This approach is perfect for standalone scripts:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beancount-no-sparebank1",
# ]
# ///

import beangulp
import beancount_no_sparebank1

importers = [
    beancount_no_sparebank1.deposit.DepositAccountImporter(
        'Assets:Bank:SpareBank1:Checking',
        currency='NOK',
        narration_to_account_mappings=[
            ('KIWI', 'Expenses:Groceries'),
            ('MENY', 'Expenses:Groceries'),
            ('VINMONOPOLET', 'Expenses:Alcohol'),
            ('STATOIL', 'Expenses:Transportation:Fuel'),
            ('RUTER', 'Expenses:Transportation:PublicTransport'),
            ('POWER', 'Expenses:Electronics'),
            ('XXL SPORT', 'Expenses:Clothing:SportGear'),
            ('FINN.NO', 'Expenses:Services:Online'),
            ('GET/TELIA', 'Expenses:Utilities:Internet'),
            ('HUSLEIE', 'Expenses:Housing:Rent'),
            ('SKATTEETATEN', 'Income:Government:TaxReturn'),
            ('Lønn', 'Income:Salary'),
            ('OBS BYGG', 'Expenses:HomeImprovement'),
            ('Overføring', 'Assets:Bank:SpareBank1:Transfer'),
        ],
        from_account_mappings=[
            ('12345678901', 'Assets:Bank:SpareBank1:Checking')
        ],
        to_account_mappings=[
            ('98712345678', 'Assets:Bank:SpareBank1:Savings')
        ]
    ),
    beancount_no_sparebank1.balance.PDFStatementImporter(
        'Assets:Bank:SpareBank1:Checking',
        currency='NOK'
    ),
]

if __name__ == '__main__':
    ingest = beangulp.Ingest(importers)
    ingest()
```

Save this as `import_sparebank1.py` and run it with:

```bash
uv run import_sparebank1.py
```

The `uv` tool will automatically create an isolated environment and install the required dependencies.

You can also find a complete example in [`examples/uv_script_example.py`](examples/uv_script_example.py).

### Option 2: Using uv project

For more complex setups or when you want to manage multiple scripts together, create a `uv` project:

```bash
# Initialize a new uv project
uv init my-beancount-project
cd my-beancount-project

# Add the dependency
uv add beancount-no-sparebank1
```

This will create a `pyproject.toml` file and manage dependencies for you. Then create your import script without the dependency declarations:

```python
import beangulp
import beancount_no_sparebank1

# ... same importer configuration as above ...

if __name__ == '__main__':
    ingest = beangulp.Ingest(importers)
    ingest()
```

Run your script with:

```bash
uv run python import_sparebank1.py
```

You can also find a complete example in [`examples/project_example.py`](examples/project_example.py).

### Option 3: Traditional approach

If you prefer using pip or other package managers:

```bash
pip install beancount-no-sparebank1
```

Then use the same Python code as in Option 2 (without the `# /// script` block).

## See also

- [Automatically balancing Beancount DKB transactions](https://sgoel.dev/posts/automatically-balancing-beancount-dkb-transactions/)
- [siddhantgoel/beancount-dkb](https://github.com/siddhantgoel/beancount-dkb)

