# CLAUDE.md

## Python Environment

Always use the virtual environment at `.venv`. Never install packages
using system pip or outside the venv.

Before any session involving Python or pip, activate the environment:
    source .venv/bin/activate

If `.venv` does not exist, create it first:
    python3 -m venv .venv
    source .venv/bin/activate

## Installing Packages

Use the venv silently — no need to ask before installing. After any
new package is installed, update requirements.txt:
    pip freeze > requirements.txt

## Running the App

    source .venv/bin/activate && streamlit run app.py

## Secrets

`.streamlit/secrets.toml` is gitignored and must never be committed.
Use `.streamlit/secrets.toml.example` as a template.
On Streamlit Cloud, enter secrets via the web dashboard.

## Code Changes

For any non-trivial change, append an entry to CHANGELOG.md with the
date and a one-line description.
