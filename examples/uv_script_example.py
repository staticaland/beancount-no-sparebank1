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
    print("beancount-no-sparebank1 example script")
    print("Package imported successfully!")
    print("Configured importers:")
    for i, importer in enumerate(importers, 1):
        print(f"  {i}. {importer.__class__.__name__}")
    
    # In a real scenario, you would run:
    # ingest = beangulp.Ingest(importers)
    # ingest()
    print("\nTo actually run the import, uncomment the ingest lines and provide CSV/PDF files.")