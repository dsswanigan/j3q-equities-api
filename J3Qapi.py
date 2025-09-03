from fastapi import FastAPI, Query, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from typing import Optional
import sqlite3
from datetime import datetime, timedelta
import os
import csv

app = FastAPI(
    title="J3Q Equities Prediction API",
    description="""API for accessing simulation results stored in SQLite.
    
Endpoints:
- `/tables` → List all tables and their columns.
- `/preview` → Preview the first N rows of any table.
- `/equity` → Retrieve equity curve data, optionally in curve-only mode.
- `/performance` → Retrieve performance metrics, optionally filtered by metric names.
- `/trades` → Retrieve trade history for a symbol/horizon/date range.
""",
    version="1.0.0"
)

# Base directory where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Allow override via environment variable, else default to local file in same folder
DB_PATH = os.environ.get("SIM_DB_PATH", os.path.join(BASE_DIR, "simulation_results.db"))

# Load allowed API keys from CSV and/or environment variable
API_KEYS = set()
API_KEY_FILE = os.path.join(BASE_DIR, "api_keys.csv")

# Option 1: Load from CSV if present
if os.path.exists(API_KEY_FILE):
    with open(API_KEY_FILE, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if "api_key" in row:
                API_KEYS.add(row["api_key"])
else:
    print(f"⚠ Warning: API key file not found at {API_KEY_FILE}")

# Option 2: Load from environment variable (comma-separated keys)
env_keys = os.environ.get("API_KEYS")
if env_keys:
    for key in env_keys.split(","):
        key = key.strip()
        if key:
            API_KEYS.add(key)

if not API_KEYS:
    print("⚠ Warning: No API keys loaded from CSV or environment variable.")

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header in API_KEYS:
        return api_key_header
    raise HTTPException(status_code=401, detail="Unauthorized")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def default_date_range(start_date: Optional[str], end_date: Optional[str]):
    today = datetime.today().date()
    if not end_date:
        end_date = today.strftime("%Y-%m-%d")
    if not start_date:
        six_months_ago = today - timedelta(days=182)
        start_date = six_months_ago.strftime("%Y-%m-%d")
    return start_date, end_date

def fetch_all_columns(table_name: str):
    with get_connection() as conn:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        return [row["name"] for row in cur.fetchall()]

def table_exists(table_name: str) -> bool:
    with get_connection() as conn:
        res = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        return res is not None

@app.get("/tables", dependencies=[Depends(get_api_key)], summary="List all tables and their columns")
def list_tables():
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    schema = {}
    for t in tables:
        table_name = t["name"]
        schema[table_name] = fetch_all_columns(table_name)
    return schema

@app.get("/preview", dependencies=[Depends(get_api_key)], summary="Preview rows from a table")
def preview_table(
    table: str = Query(..., description="Name of the table to preview"),
    limit: int = Query(5, description="Number of rows to return")
):
    if not table_exists(table):
        return {"error": f"Table '{table}' not found in database."}
    cols = fetch_all_columns(table)
    if not cols:
        return {"error": f"Table '{table}' has no columns."}
    query = f"SELECT * FROM {table} LIMIT ?"
    with get_connection() as conn:
        rows = conn.execute(query, (limit,)).fetchall()
    return [dict(r) for r in rows]

@app.get("/equity", dependencies=[Depends(get_api_key)], summary="Retrieve equity curve data")
def get_equity(
    symbol: Optional[str] = Query(None, description="Symbol to filter by"),
    horizon: Optional[str] = Query(None, description="Horizon to filter by"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    curve_only: bool = Query(False, description="If true, return only date, equity_model, equity_bh columns")
):
    if not table_exists("equity"):
        return {"error": "Table 'equity' not found in database."}

    cols = fetch_all_columns("equity")
    start_date, end_date = default_date_range(start_date, end_date)
    filters, params = [], []

    if symbol and "symbol" in cols:
        filters.append("symbol = ?")
        params.append(symbol)
    if horizon and "horizon" in cols:
        filters.append("horizon = ?")
        params.append(horizon)
    if "date" in cols:
        filters.append("date >= ? AND date <= ?")
        params.extend([start_date, end_date])

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    select_cols = ["date", "equity_model", "equity_bh"] if curve_only and all(c in cols for c in ["date", "equity_model", "equity_bh"]) else cols

    query = f"SELECT {', '.join(select_cols)} FROM equity {where_clause} ORDER BY {select_cols[0]}"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@app.get("/performance", dependencies=[Depends(get_api_key)], summary="Retrieve performance metrics")
def get_performance(
    symbol: Optional[str] = Query(None, description="Symbol to filter by"),
    horizon: Optional[str] = Query(None, description="Horizon to filter by"),
    metrics: Optional[str] = Query(None, description="Comma-separated list of metrics to include")
):
    if not table_exists("performance"):
        return {"error": "Table 'performance' not found in database."}

    cols = fetch_all_columns("performance")
    filters, params = [], []

    if symbol and "symbol" in cols:
        filters.append("symbol = ?")
        params.append(symbol)
    if horizon and "horizon" in cols:
        filters.append("horizon = ?")
        params.append(horizon)
    if metrics and "metric" in cols:
        metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
        placeholders = ",".join("?" * len(metric_list))
        filters.append(f"metric IN ({placeholders})")
        params.extend(metric_list)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = f"SELECT * FROM performance {where_clause}"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

@app.get("/trades", dependencies=[Depends(get_api_key)], summary="Retrieve trade history")
def get_trades(
    symbol: Optional[str] = Query(None, description="Symbol to filter by"),
    horizon: Optional[str] = Query(None, description="Horizon to filter by"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    if not table_exists("trades"):
        return {"error": "Table 'trades' not found in database."}

    cols = fetch_all_columns("trades")
    start_date, end_date = default_date_range(start_date, end_date)
    filters, params = [], []

    if symbol and "symbol" in cols:
        filters.append("symbol = ?")
        params.append(symbol)
    if horizon and "horizon" in cols:
        filters.append("horizon = ?")
        params.append(horizon)
    if "trade_date" in cols:
        filters.append("trade_date >= ? AND trade_date <= ?")
        params.extend([start_date, end_date])

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = f"SELECT * FROM trades {where_clause} ORDER BY trade_date"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

if __name__ == "__main__":
    print("🔍 Self-test: Inspecting database schema and sample data...")
    schema = list_tables()
    for table, columns in schema.items():
        print(f"\n=== Table: {table} ===")
        print(f"Columns: {columns}")
        preview = preview_table(table, limit=3)
        print(f"Sample rows ({len(preview)}):")
        for row in preview:
            print(row)
