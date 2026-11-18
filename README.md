# Mule Buster

Mule Buster is a hackathon prototype for **simulated** money-mule detection at **one bank**.

A money mule account is an account used to pass illegal funds onward. This project practices finding those patterns in **fake data**. It does not connect to a real bank, and it does not contain detection logic yet.

What you have today is the folder structure, the library list, a working fake-data generator, and a placeholder web page.

## Folder map

| Folder | Future job |
| --- | --- |
| `data_generation/` | Build fake accounts and transactions |
| `data/raw/` | Save generated input files |
| `data/processed/` | Save cleaned files |
| `bank_ai/` | Score accounts using only this bank's data |
| `central_ai/` | Reserved for a later multi-bank comparison |
| `detection/` | Turn scores into risk levels and alerts |
| `dashboard/` | Show results in the browser with Streamlit |
| `database/` | Store simulated records in SQLite |
| `tests/` | Small checks that the pieces import |

`app.py` is the file you run. It opens the placeholder page in `dashboard/home.py`.

## Libraries

| Library | Why it is here |
| --- | --- |
| Streamlit | Local web page |
| Pandas | Tables of simulated accounts and transactions |
| NumPy | Numbers used by the future model |
| Scikit-learn | Future Bank AI model |
| NetworkX | Future graph of how accounts pay each other |
| Plotly | Future charts on the dashboard |
| SQLite | File database that ships inside Python as `sqlite3` |

SQLite is not listed in `requirements.txt` because you do not install it separately.

## Set up the virtual environment

A virtual environment is a private folder of libraries for this project. Installing here does not change other Python projects on your computer.

The steps below were written for **Windows PowerShell**. Run them from the folder where you cloned this project.

`python` by itself may open the Microsoft Store instead of real Python. Use `py -3.15`, which selects Python 3.15 already installed on this PC.

### 1. Open the project folder in the terminal

`cd` means change directory. It moves the terminal into the project folder. Commands you type afterward apply to this project.

```powershell
cd "the folder where you cloned this project"
```

### 2. Create the virtual environment

`py -3.15` starts Python 3.15. `-m venv` runs Python's built-in environment builder. `.venv` is the new folder that will hold this project's private Python.

```powershell
py -3.15 -m venv .venv
```

You only create `.venv` once per computer. If that folder already exists, skip this command.

### 3. Turn the virtual environment on

This command applies to the current terminal window. When it works, the prompt starts with `(.venv)`.

```powershell
.\.venv\Scripts\Activate.ps1
```

The `.\` means "in this folder". `Activate.ps1` is the PowerShell switch that makes `python` and `streamlit` point at `.venv`.

If PowerShell says running scripts is disabled, allow scripts for **this window only**, then try the activate command again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

`Set-ExecutionPolicy` changes a Windows safety setting. `-Scope Process` limits that change to the current terminal window. Closing the window clears it.

### 4. Install the libraries

`pip` is Python's library installer. `-m pip` runs it through Python. `-r requirements.txt` reads the package names from that file and installs them into the active environment.

With `(.venv)` visible on the prompt:

```powershell
python -m pip install -r requirements.txt
```

If you have not activated `.venv`, this still installs into the project environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the placeholder page

`streamlit` starts a local website. `run app.py` tells it which file to open. Leave this terminal running while you use the page.

With `(.venv)` visible:

```powershell
streamlit run app.py
```

Without activation:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit prints a local address, usually `http://localhost:8501`. Open that address if the browser does not open by itself.

The first time, Streamlit may ask for an email. You can press Enter to skip it.

To stop the page, click the terminal and press `Ctrl+C`.

## Generate the fake bank data

This writes three files for the single-bank prototype:

- `data/raw/accounts.csv` — 100 fake accounts
- `data/raw/transactions.csv` — 320 fake payments
- `data/raw/summary_report.txt` — counts of accounts, payments, and ground-truth labels

Ground-truth labels are the answers baked into the fake story. They are separate from anything a model might guess later. The file has no prediction column.

The generator uses a fixed random seed, `42`, so running it again produces the same `BANK_01` files. The same stories can later be replayed for `BANK_02` and `BANK_03` with different account IDs and dates. Only `BANK_01` is written by the command below.

With `(.venv)` visible, from the project folder:

```powershell
python -m data_generation.data_generator
```

`python -m` runs a Python file as a module. `data_generation.data_generator` is the generator. It prints the summary, then the paths of the three files.

Without activation:

```powershell
.\.venv\Scripts\python.exe -m data_generation.data_generator
```

## Run the checks

`unittest` is Python's built-in test runner. `discover -s tests` looks in the `tests` folder for files named `test_*.py` and runs them. The data tests check the fake ledger. The scaffold tests check that the unfinished modules still import.

With `(.venv)` visible, from the project folder:

```powershell
python -m unittest discover -s tests
```

## Git

Git is not installed on this PC, so this folder is not a Git repository yet. The project still runs without Git.

When you want saved history, install Git for Windows from [https://git-scm.com/download/win](https://git-scm.com/download/win). Then, in this folder, run:

```powershell
git init
```

`git init` creates a hidden `.git` folder that can record future versions. It does not upload anything.

## What is intentionally missing

- A trained model
- Risk rules and alerts
- Charts and account graphs
- A created SQLite database

Read `PROJECT_CONTEXT.md` for what each module is meant to become.
