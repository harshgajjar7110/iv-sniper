# GEMINI.MD: AI Collaboration Guide

This document provides essential context for AI models interacting with this project. Adhering to these guidelines will ensure consistency and maintain code quality.

## 1. Project Overview & Purpose

* **Primary Goal:** Automate the identification of High IV/IVP stocks in the Indian F&O market, locate key support/resistance via Volume Profile, and execute defined-risk Credit Spreads with automated exits on Zerodha.
* **Project Code Name:** IV-Sniper
* **Business Domain:** Quantitative Finance / Options Trading Automation

## 2. Core Technologies & Stack

* **Languages:** Python 3.11
* **Frameworks & Runtimes:** CPython, Zerodha Kite Connect SDK
* **Databases:** SQLite (local, WAL mode)
* **Key Libraries/Dependencies:**
    - `kiteconnect` — Zerodha broker API SDK
    - `pandas`, `numpy` — Data manipulation and numerical computing
    - `scipy` — Black-Scholes IV inversion (Newton-Raphson via `scipy.stats.norm`)
    - `schedule` — Cron-style task scheduling
* **Package Manager(s):** pip (requirements.txt)

## 3. Architectural Patterns

* **Overall Architecture:** Modular monolith — five pipeline stages (Data Ingestion → Scanner → Analyst → Executor → Watchdog) within a single codebase.
* **Directory Structure Philosophy:**
    - `/core` — Core computation and API modules (Kite client, HV/IV calculators, trend detector, instrument master)
    - `/scanner` — Scanner module: IV/IVP scoring + trend filtering (Chunk 2 deliverable)
    - `/analyst` — Analyst module: Volume Profile, strike selection, spread construction (Chunk 3 deliverable)
    - `/executor` — Execution Engine: Risk guards, order placement, trade logging (Chunk 4 deliverable)
    - `/watchdog` — Watchdog: Monitor open positions & auto-exit on Target/SL/Expiry (Chunk 5 deliverable)
    - `/db` — Database connection management and schema definitions
    - `/data` — Runtime-generated SQLite database files (gitignored)
    - `/tests` — Unit tests using `unittest`
    - `config.py` — Central configuration with env-var-backed secrets
    - `daily_iv_logger.py` — Cron job entry point (Chunk 1 deliverable)
    - `run_scanner.py` — Scanner CLI entry point (Chunk 2 deliverable)
    - `run_analyst.py` — Analyst CLI entry point (Chunk 3 deliverable)
    - `run_executor.py` — Main Execution Pipeline (Chunk 4 deliverable)
    - `watchdog_job.py` — Watchdog daemon/cron entry point (Chunk 5 deliverable)

## 4. Coding Conventions & Style Guide

* **Formatting:** 4-space indentation. Follow PEP 8. Max line length ~88 (Black-compatible).
* **Naming Conventions:**
    - `variables`, `functions`: snake_case (`calculate_hv`)
    - `classes`: PascalCase (`KiteClient`)
    - `constants`: UPPER_SNAKE_CASE (`TRADING_DAYS_PER_YEAR`)
    - `files`: snake_case (`iv_calculator.py`)
    - Private helpers: prefixed with `_` (`_d1`, `_save_iv_record`)
* **Docstrings:** NumPy-style with Parameters/Returns/Raises sections.
* **Error Handling:** Explicit exception handling with logging. API calls use exponential backoff. Functions return `None` on non-convergence rather than raising.

## 5. Key Files & Entrypoints

* **Main Entrypoints:**
    - `daily_iv_logger.py` — Daily IV snapshot cron job (Chunk 1)
    - `run_scanner.py` — Scanner CLI for filtering candidates (Chunk 2)
    - `run_analyst.py` — Analyst CLI: VP + spread builder (Chunk 3)
    - `run_executor.py` — Main Pipeline: Scan → Analyze → Execute (Chunk 4)
    - `watchdog_job.py` — Watchdog Monitor: Exit management (Chunk 5)
* **Configuration:** `config.py` (reads from `.env` via `python-dotenv`)
* **Database Init:** `python -m db.schema`

## 6. Development & Testing Workflow

* **Setup:**
    1. `python -m venv venv && venv\Scripts\activate`
    2. `pip install -r requirements.txt`
    3. Create `.env` with: `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_ACCESS_TOKEN`
    4. `python -m db.schema` (create tables)
* **Run:**
    - `python daily_iv_logger.py --once` (test IV snapshot)
    - `python daily_iv_logger.py` (scheduled daily @ 15:25 IST)
    - `python run_scanner.py --top 5 --min-score 50` (scan for candidates)

## 7. Specific Instructions for AI Collaboration

* **Security:** Never hardcode API keys. All secrets via environment variables. The `.env` file is gitignored.
* **Dependencies:** Add to `requirements.txt` with version ranges. Run `pip install -r requirements.txt`.
* **Database:** Use `db.connection.get_connection()` context manager for all DB access. Never raw `sqlite3.connect()`.
* **Broker API:** Use `core.kite_client.KiteClient` for all Zerodha calls. Never import `kiteconnect` directly elsewhere.
* **Commit Messages:** Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`).
