# Feature Request: Support metadata/field-based pattern matching in TransactionPattern

## Repository

https://github.com/staticaland/beancount-no-amex

## Summary

Add support for matching transactions based on arbitrary metadata fields, not just narration and amount. This would make the classifier truly generic and usable across different import formats.

## Motivation

When integrating `beancount-no-amex`'s classifier into `beancount-no-sparebank1`, I encountered a limitation: SpareBank 1 CSV files include bank account numbers (`Fra konto` / `Til konto`) that are useful for categorization.

Currently, the classifier only supports:
- `narration` - string/regex matching
- `amount_condition` - numeric comparisons

But many import formats have additional fields that would be useful for matching:
- **Bank account numbers** (SpareBank 1 CSV: `Fra konto`, `Til konto`)
- **Transaction types** (OFX: `TRNTYPE` like `DEBIT`, `CREDIT`, `ATM`)
- **Merchant category codes** (MCC codes in card transactions)
- **Reference numbers** or **transaction IDs**

## Proposed Solution

Add a `metadata` or `fields` parameter to `TransactionPattern` that accepts a dictionary of field names to match patterns:

```python
# Option A: Simple equality matching
TransactionPattern(
    fields={"to_account": "98712345678"},
    account="Assets:Bank:Savings",
)

# Option B: Pattern matching with operators
TransactionPattern(
    fields={
        "to_account": FieldCondition(equals="98712345678"),
        # or
        "transaction_type": FieldCondition(in_=["ATM", "DEBIT"]),
        # or
        "merchant_code": FieldCondition(regex=r"5411|5412"),  # Grocery MCCs
    },
    account="Expenses:Groceries",
)

# Option C: Simple dict with string patterns (like narration matching)
TransactionPattern(
    fields={"to_account": "98712345678"},  # Exact match
    account="Assets:Bank:Savings",
)
TransactionPattern(
    fields={"merchant_name": "REMA"},  # Substring match
    regex_fields={"merchant_name"},  # Opt-in to regex
    account="Expenses:Groceries",
)
```

## Changes Required

### 1. Update `TransactionPattern` model

```python
class TransactionPattern(BaseModel):
    narration: str | None = None
    regex: bool = False
    case_insensitive: bool = False
    amount_condition: AmountCondition | None = None

    # New: field-based matching
    fields: dict[str, str] | None = None  # field_name -> pattern
    fields_regex: bool = False  # Apply regex matching to field patterns

    account: str | None = None
    splits: list[AccountSplit] | None = None
    shared_with: list[SharedExpense] | None = None
```

### 2. Update `matches()` method

```python
def matches(self, narration: str, amount: Decimal, fields: dict[str, str] | None = None) -> bool:
    # Existing narration check...
    # Existing amount check...

    # New: field matching
    if self.fields is not None and fields is not None:
        for field_name, pattern in self.fields.items():
            field_value = fields.get(field_name, "")
            if self.fields_regex:
                if not re.search(pattern, field_value):
                    return False
            else:
                if pattern not in field_value:
                    return False

    return True
```

### 3. Update `TransactionClassifier.classify()`

```python
def classify(
    self,
    narration: str,
    amount: Decimal,
    fields: dict[str, str] | None = None,  # New parameter
) -> ClassificationResult | None:
```

### 4. Update `ClassifierMixin.finalize()`

The mixin would need a way to extract fields from the row. Options:
- Add a `get_fields(row) -> dict` method that subclasses override
- Accept fields as a parameter to `finalize()`

## Example Usage in SpareBank 1

```python
from beancount_no_amex.classify import TransactionPattern

config = Sparebank1AccountConfig(
    transaction_patterns=[
        # Match by bank account number
        TransactionPattern(
            fields={"to_account": "98712345678"},
            account="Assets:Bank:Savings",
        ),
        # Match by narration (existing)
        TransactionPattern(
            narration="KIWI",
            account="Expenses:Groceries",
        ),
        # Combine field + narration matching
        TransactionPattern(
            fields={"transaction_type": "ATM"},
            amount_condition=amount > 500,
            account="Expenses:Cash:Large",
        ),
    ],
)
```

## Benefits

1. **Truly generic classifier** - Works with any import format
2. **Single pattern syntax** - Users learn one API for all matching
3. **Composable conditions** - Combine field, narration, and amount matching
4. **Backward compatible** - Existing patterns still work

## Alternatives Considered

1. **Keep format-specific logic in importers** (current workaround)
   - Pros: Simple, no changes to amex
   - Cons: Duplicated logic, inconsistent APIs across importers

2. **Callback/hook system for custom matching**
   - Pros: Maximum flexibility
   - Cons: More complex, less declarative

## Current Workaround

In `beancount-no-sparebank1`, we handle bank account matching separately in `finalize()` before calling the classifier:

```python
def finalize(self, txn, row):
    # 1. Check bank account mappings first (format-specific)
    account_to_check = to_account if txn_amount < 0 else from_account
    for pattern, acc in self.other_account_mappings:
        if pattern == account_to_check:
            return self._add_posting(txn, acc)

    # 2. Fall back to classifier for narration matching
    if result := self._classifier.classify(narration, txn_amount):
        return self._classifier.add_balancing_postings(txn, result)
```

This works but requires maintaining two separate matching systems.
