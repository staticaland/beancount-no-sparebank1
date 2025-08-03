#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beancount-no-sparebank1",
# ]
# ///

import beangulp
import beancount_no_sparebank1

def main():
    print("=== UV Script Dependencies Demo ===")
    print("This script demonstrates the uv script dependencies approach")
    print("with the beancount-no-sparebank1 package.")
    
    # Create configuration for the deposit account importer
    deposit_config = beancount_no_sparebank1.deposit.Sparebank1AccountConfig(
        primary_account_number='12345678901',
        account_name='Assets:Bank:SpareBank1:Checking',
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
        other_account_mappings=[
            ('98712345678', 'Assets:Bank:SpareBank1:Savings')
        ]
    )

    importers = [
        beancount_no_sparebank1.deposit.DepositAccountImporter(deposit_config),
        beancount_no_sparebank1.balance.PDFStatementImporter(
            'Assets:Bank:SpareBank1:Checking',
            currency='NOK'
        ),
    ]
    
    print("✅ beancount-no-sparebank1 imported successfully!")
    print("✅ Configuration created successfully!")
    print("✅ Importers initialized successfully!")
    
    print("\nConfigured importers:")
    for i, importer in enumerate(importers, 1):
        print(f"  {i}. {importer.__class__.__name__}")
        print(f"     - Account: {importer.account_name}")
        print(f"     - Currency: {importer.currency}")
    
    print(f"\nDeposit account configuration:")
    print(f"  - Primary account: {deposit_config.primary_account_number}")
    print(f"  - Account name: {deposit_config.account_name}")
    print(f"  - Currency: {deposit_config.currency}")
    print(f"  - Narration mappings: {len(deposit_config.narration_to_account_mappings)}")
    print(f"  - Other account mappings: {len(deposit_config.other_account_mappings)}")
    
    print("\n🎉 UV script dependencies approach working perfectly!")
    print("This demonstrates how you can create a self-contained script")
    print("that automatically installs beancount-no-sparebank1 when run.")
    
    # In a real scenario, you would run:
    # ingest = beangulp.Ingest(importers)
    # ingest()
    print("\nTo actually run the import, uncomment the ingest lines and provide CSV/PDF files.")

if __name__ == '__main__':
    main()