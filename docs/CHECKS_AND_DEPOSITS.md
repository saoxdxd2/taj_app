# Checks and Customer Deposits

This note documents how a physical check is linked to a sale and what
happens when it bounces or is cancelled.

## Check lifecycle

```
Pending ──► Deposited ──► Cleared
   │             │
   │             └──────► Bounced ──► Deposited
   └──► Cleared                       └──► Cancelled
   └──► Cancelled
```

`Cleared` is final: clearing a check posts the journal entry exactly once.

## Linking a check to an invoice or deposit

A `Check` payment or `Check` customer deposit must carry a `check_id`.
`SalesService` validates that the check:

- exists and is **incoming**;
- belongs to the same customer as the invoice/deposit;
- has an amount **exactly equal** to the payment/deposit;
- is `Pending`, `Deposited` or `Cleared`; and
- is not already linked to another payment or deposit.

The strict amount equality is deliberate. The current schema does not track
how much of a check has been consumed, so allowing partial allocation would
make the journal entry and the invoice payments diverge. To use a larger
check, record it as a customer deposit and apply the deposit in parts.

A `Cleared` check can still be linked if it has not been used before: its
receipt is already in the journal, and the link only allocates that money to
an invoice. `register_payment` does not post a second receipt for `Check`
payments.

## Why the link matters

`Cash` and `Bank Transfer` payments post a journal entry immediately.
`Check` payments defer the receipt until the check clears, so the invoice is
marked paid while the money is still expected. Without a `check_id`, there
is no check for `FinanceService.update_check_status` to clear and the
receipt would never reach the journal.

## Bouncing or cancelling

A check that bounces or is cancelled **before clearing** has no journal
entry yet. The service therefore:

1. deletes the provisional payment(s) linked to the check;
2. cancels the linked customer deposit, restores its `amount_used`, and
   releases the check link so a cured check can back a new deposit;
3. reopens affected invoices (`Paid` -> `Validated`); and
4. leaves the check in `Bounced` or `Cancelled`.

The deleted payments remain visible in the audit trail. A check that has
already been `Cleared` cannot be bounced in this workflow.

## UI flow

1. **Finance → New Check**: register the paper, its customer and amount.
2. **Sales → Register Payment** (or **New Customer Deposit**): choose
   `Check` and select the unused check.
3. **Finance → Checks**: deposit and, later, clear the check. Clearing
   posts the receipt.

If no check is listed in the sales dialog, register it in Finance first or
check that it is not already linked to another document.
