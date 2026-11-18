"""Future home of the single-bank scoring model."""


def score_accounts(accounts, transactions):
    """Return a not-ready note until the bank model is written."""
    return {
        "ready": False,
        "message": "Bank AI scoring is not built yet.",
        "accounts_received": accounts is not None,
        "transactions_received": transactions is not None,
    }
