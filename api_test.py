import requests
import json
import pandas as pd
import sys

BASE_URL = "http://127.0.0.1:8000"

# 🔑 Your API key (must match what's in api_keys.csv)
API_KEY = "MY_SUPER_SECRET_KEY_123"
HEADERS = {"x-api-key": API_KEY}

all_tests_passed = True  # Will flip to False if any test fails

def test_endpoint(path, params=None, expect_nonempty=False):
    """Call an endpoint, print status, and display results nicely."""
    global all_tests_passed
    print(f"=== {path} | params={params} ===")
    try:
        r = requests.get(f"{BASE_URL}{path}", params=params or {}, headers=HEADERS)
    except Exception as e:
        print(f"❌ Request failed: {e}")
        all_tests_passed = False
        return None

    print("Status:", r.status_code)
    if r.status_code != 200:
        all_tests_passed = False

    try:
        data = r.json()
    except Exception:
        print("Raw response:", r.text)
        all_tests_passed = False
        return None

    if expect_nonempty and (not data or (isinstance(data, list) and len(data) == 0)):
        print("⚠ Expected non-empty result but got empty.")
        all_tests_passed = False

    if isinstance(data, dict):
        print(json.dumps(data, indent=4))
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            print(pd.DataFrame(data).head())
        else:
            print(json.dumps(data, indent=4))
    else:
        print(data)
    print()
    return data

# 1️⃣ Get schema
tables = test_endpoint("/tables", expect_nonempty=True)
if not tables or not isinstance(tables, dict):
    sys.exit(1)

# 2️⃣ Helper to get (symbol, horizon) pairs from a table
def get_pairs(table, symbol_col="symbol", horizon_col="horizon"):
    if table not in tables:
        return set()
    preview = test_endpoint("/preview", {"table": table, "limit": 1000})
    return set(
        (row.get(symbol_col), row.get(horizon_col))
        for row in preview
        if row.get(symbol_col) and row.get(horizon_col)
    )

# 3️⃣ Find common (symbol, horizon) across all relevant tables
pairs_trades = get_pairs("trades")
pairs_equity = get_pairs("equity")
pairs_perf = get_pairs("performance")

common_pairs = pairs_trades & pairs_equity & pairs_perf
if not common_pairs:
    print("⚠ No common (symbol, horizon) found across all tables.")
    symbol_sample, horizon_sample = None, None
else:
    symbol_sample, horizon_sample = next(iter(common_pairs))
    print(f"✅ Using sample pair: symbol={symbol_sample}, horizon={horizon_sample}")

# 4️⃣ Pick a sample metric if available
metric_sample = None
if "performance" in tables:
    preview_perf = test_endpoint("/preview", {"table": "performance", "limit": 50})
    if preview_perf:
        metric_sample = preview_perf[0].get("metric")
        if metric_sample:
            print(f"✅ Using sample metric: {metric_sample}")

# 5️⃣ Test /preview for all tables
for t in tables.keys():
    test_endpoint("/preview", {"table": t, "limit": 3})

# 6️⃣ Test /equity in both modes
if symbol_sample and horizon_sample:
    for curve_only in [False, True]:
        test_endpoint("/equity", {
            "symbol": symbol_sample,
            "horizon": horizon_sample,
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "curve_only": curve_only
        })

# 7️⃣ Test /performance with and without metrics filter
if symbol_sample and horizon_sample:
    test_endpoint("/performance", {
        "symbol": symbol_sample,
        "horizon": horizon_sample
    })
    if metric_sample:
        test_endpoint("/performance", {
            "symbol": symbol_sample,
            "horizon": horizon_sample,
            "metrics": metric_sample
        })

# 8️⃣ Test /trades with date range
if symbol_sample and horizon_sample:
    test_endpoint("/trades", {
        "symbol": symbol_sample,
        "horizon": horizon_sample,
        "start_date": "2024-01-01",
        "end_date": "2024-06-30"
    })

# 9️⃣ Exit with status code for batch file
if all_tests_passed:
    print("🎉 All API tests completed successfully — no errors or warnings.")
    sys.exit(0)
else:
    print("⚠ Some API tests failed or returned warnings. Check the output above.")
    sys.exit(1)
