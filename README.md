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

``` python
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

## See also

- [Automatically balancing Beancount DKB transactions](https://sgoel.dev/posts/automatically-balancing-beancount-dkb-transactions/)
- [siddhantgoel/beancount-dkb](https://github.com/siddhantgoel/beancount-dkb)

