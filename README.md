# Mule Buster

Mule Buster is a hackathon prototype for **simulated** money-mule detection at **one bank**.

A money mule account is an account used to pass illegal funds onward. This project practices finding those patterns in **synthetic data**. It does not connect to a real bank or read real customer data.

The project includes synthetic data generation, single-bank risk scoring and classification (Bank AI), cross-account graph topology and chain analysis (Central AI), instant transaction detection, SQLite persistence, and a Streamlit command center dashboard.

## Folder map

| Folder | Job |
| --- | --- |
| `data_generation/` | Build fake accounts and transactions using a deterministic seed |
| `data/raw/` | Save generated input CSV files |
| `data/processed/` | Save cleaned and feature-engineered datasets |
| `bank_ai/` | Score accounts using single-bank features, rules, and machine learning |
| `central_ai/` | Multi-hop graph and temporal kill-chain detection |
| `detection/` | Instant transaction risk assessment and rule engine |
| `dashboard/` | Interactive analyst command center built with Streamlit |
| `database/` | Persistent local SQLite database and schemas |
| `tests/` | Automated unit, scaffold, pipeline, and label leakage tests |

`app.py` is the main entry point that launches the Streamlit application.

## Libraries

| Library | Why it is here |
| --- | --- |
| Streamlit | Local web application and interactive user interface |
| Pandas | Ingestion, filtering, and table transformations for simulated accounts and transactions |
| NumPy | Numerical arrays and mathematical operations for features and scoring |
| Scikit-learn | Supervised classification model training and evaluation |
| LightGBM | Gradient boosting models with monotonic constraints for account risk scoring |
| SHAP | Model explainability and feature contribution reason codes |
| NetworkX | Graph data structures for account-to-account payment network topologies (installed & used) |
| Plotly | Interactive charts, distribution plots, and network visualizations (installed & used) |
| Pydantic & Pandera | Strict schema validation for data models, entities, and transactions |
| Ruamel.yaml | Configuration file loading for tunable detection rules and thresholds |
| SQLite | File database that ships with standard Python as `sqlite3` (no separate install required) |

## Prerequisites

- **Python**: Python 3.10 or higher (tested on Python 3.11, 3.12, and 3.15). Any recent Python 3.10+ release with standard packaging tools should work.
- **Git**: Required for version control and cloning this repository.

## Set up the virtual environment

A virtual environment is a private folder of libraries for this project. Installing here does not change other Python installations on your machine.

Open your terminal, navigate to the folder where you cloned this repository, and follow the steps below:

### 1. Create the virtual environment

- **Windows (PowerShell or Command Prompt)**:
  ```powershell
  python -m venv .venv
  ```
  *(If `python` opens the Microsoft Store on Windows, try `py -m venv .venv`)*

- **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  ```

You only need to create `.venv` once per machine.

### 2. Activate the virtual environment

- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  *Note on PowerShell Execution Policy:* If PowerShell displays a script execution error, set the execution policy to `RemoteSigned` for your current process:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\.venv\Scripts\Activate.ps1
  ```
  `RemoteSigned` permits locally authored scripts (like virtual environment activation) to run while blocking unsigned remote scripts. `-Scope Process` ensures this change only affects the current terminal window.

- **Windows (Command Prompt)**:
  ```cmd
  .\.venv\Scripts\activate.bat
  ```

- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

When activated, your terminal prompt will be prefixed with `(.venv)`.

### 3. Install the dependencies

With the virtual environment activated:

```bash
python -m pip install -r requirements.txt
```

## Run the dashboard

Start the local Streamlit application:

```bash
streamlit run app.py
```

Streamlit will print a local URL (typically `http://localhost:8501`). Open it in your web browser.

**To stop the page:** Click in the terminal running Streamlit and press `Ctrl+C`.

## Generate synthetic bank data

The data generator produces realistic synthetic transaction histories for testing:

- **`data/raw/accounts.csv`** — 100 simulated accounts
- **`data/raw/transactions.csv`** — 320 simulated payment records
- **`data/raw/summary_report.txt`** — High-level summary of accounts, transactions, and archetype counts

> **Important:** Re-running the generator overwrites the files in `data/raw/`. Any manual edits made to those CSV files will be replaced.

Run the generator from the project root with your virtual environment active:

```bash
python -m data_generation.data_generator
```

### Data Schema Reference

Both CSV files include the ground-truth answers baked into the synthetic scenarios. These are labels for evaluation, not model predictions.

#### `data/raw/accounts.csv`
| Column | Type | Description |
| --- | --- | --- |
| `account_id` | String | Unique account identifier (e.g., `ACC_001`) |
| `bank_id` | String | Simulated financial institution identifier (`BANK_01`) |
| `account_role` | String | Account archetype (`CUSTOMER`, `MERCHANT`, `SMURF_HUB`, `MULE_CHAIN`, `DORMANT_MULE`) |
| `ground_truth_label` | String | Ground-truth simulation label (e.g., `0_LEGITIMATE_NORMAL`, `1_MULE_SMURF_HUB`) |
| `is_legitimate_decoy` | Boolean | True if high-activity but benign account intended to challenge false-positive rates |
| `city_code` | String | Account opening location code (e.g., `PUN`, `MUM`, `DEL`) |
| `opened_on` | Date (YYYY-MM-DD) | Date the simulated account was created |
| `opening_balance_inr` | Float | Initial ledger balance in INR |

#### `data/raw/transactions.csv`
| Column | Type | Description |
| --- | --- | --- |
| `transaction_id` | String | Unique transaction reference (e.g., `TXN_0001`) |
| `sender_id` | String | Originating account ID (references `account_id`) |
| `receiver_id` | String | Destination account ID (references `account_id`) |
| `amount` | Float | Transaction transfer amount in INR |
| `timestamp` | ISO 8601 String | Transaction timestamp with timezone offset |
| `transaction_type` | String | Payment channel (e.g., `SALARY_NEFT`, `IMPS_TRANSFER`, `UPI_TRANSFER`) |
| `ground_truth_label` | String | Scenario label indicating whether transfer is legitimate or part of a mule flow |

## Run the automated tests

Run Python's built-in test runner across the entire test suite:

```bash
python -m unittest discover -s tests
```

The test suite covers:
- Synthetic ledger consistency, deterministic seeds, and multi-bank profile isolation (`test_data_generator.py`)
- Module scaffold imports and interfaces (`test_scaffold.py`)
- Central AI graph construction, time-respecting paths, and causal monotonicity (`test_central_ai.py`)
- End-to-end instant detection, database persistence, and investigation workflows (`test_functional_pipeline.py`)
- Label leakage prevention to guarantee ground-truth labels never enter ML feature matrices (`test_label_leakage.py`)
