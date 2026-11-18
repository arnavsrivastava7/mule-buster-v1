# Project context

## Goal

Mule Buster is a hackathon prototype that will simulate how one bank could flag accounts that look like money mules. A money mule account is used to receive and pass on illegal funds. The prototype must use **synthetic data only**. It must not read real customer records or connect to a real bank.

The first version is a **single-bank** prototype. Central AI is a reserved module for a possible later version that compares summaries from more than one bank. Do not build that comparison while the single-bank path is still unfinished.

## Current status

The folder structure is in place, and the synthetic data generator works for one bank.

- `data_generation` writes `data/raw/accounts.csv`, `data/raw/transactions.csv`, and `data/raw/summary_report.txt`.
- Ground-truth labels live in `ground_truth_label`. The generator does not write model predictions.
- Bank AI, detection, the dashboard logic, the database, and Central AI are still placeholders.
- Those placeholder packages expose `STATUS = "placeholder"` and return `{"ready": False, ...}`.
- `app.py` still opens a Streamlit page that lists modules. It does not score accounts yet.
- `tests/test_data_generator.py` checks the ledger, the seed, and the three bank profiles.
- `tests/test_scaffold.py` checks that the unfinished modules still import.

## Planned flow

1. `data_generation` creates fake accounts and payments for one bank.
2. Generated files land in `data/raw`, and any cleaned files land in `data/processed`.
3. `database` stores those simulated rows in a local SQLite file.
4. `bank_ai` scores accounts from that one bank's data.
5. `detection` turns scores into risk levels and short review reasons.
6. `dashboard` shows the tables, future charts, and alerts.
7. `central_ai` stays unused until a multi-bank version is explicitly requested.

## Technology choices

- **Python** is the language for every module.
- **Pandas** and **NumPy** handle tables and numeric work.
- **Scikit-learn** is the planned home of the bank model.
- **NetworkX** is the planned home of an account-to-account payment graph inside `detection`.
- **Plotly** is the planned chart library for `dashboard`.
- **Streamlit** serves the local page through `app.py`.
- **SQLite**, through Python's `sqlite3` module, is the planned file database. There is no separate database server.

## Boundaries for later work

- Keep real account numbers, credentials, and live bank APIs out of this project.
- Keep data generation synthetic and obvious, for example by labeling records as simulated.
- Explain risk results in plain language for a beginner reviewer.
- Add behavior to the existing modules instead of collapsing everything into `app.py`.
- Leave `central_ai` as a placeholder until the single-bank path works end to end.

## How to run

Setup, the virtual environment, and the exact Windows commands live in `README.md`.
