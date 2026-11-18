"""Write the simulated single-bank dataset."""

from data_generation.data_generator import generate_dataset


def generate_bank_data(bank_id="BANK_01"):
    """Create accounts.csv and transactions.csv for one simulated bank."""
    written = generate_dataset(bank_id=bank_id)
    return {
        "ready": True,
        "message": "Synthetic accounts and transactions written.",
        "bank_id": written["bank_id"],
        "accounts_path": str(written["accounts_path"]),
        "transactions_path": str(written["transactions_path"]),
        "summary_path": str(written["summary_path"]),
    }
