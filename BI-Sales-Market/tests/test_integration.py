"""
Test 4: Integration Test — End-to-End Pipeline
Menguji alur lengkap: CoinGecko API → Python → PostgreSQL
"""

import sys
import time
import os

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api_client import CoinGeckoClient
from src.db_manager import DatabaseManager
from src.styles import S, styled_header, styled_summary


def test_end_to_end_ticker():
    """Test 4a: Full pipeline — fetch prices and insert to DB."""
    print(styled_header("TEST 4a: End-to-End Ticker Pipeline"))

    api = CoinGeckoClient()
    db = DatabaseManager()

    # Step 1: Connect to DB
    assert db.connect(), f"{S.FAILED}: Cannot connect to DB"
    print(f"  {S.OK} Step 1: DB connected")

    # Step 2: Get initial count
    initial_count = db.get_row_count("market_ticker")
    print(f"  {S.DATA} Initial row count: {initial_count}")

    # Step 3: Fetch prices from API
    start = time.time()
    prices = api.fetch_prices()
    fetch_time = time.time() - start
    assert len(prices) > 0, f"{S.FAILED}: No prices fetched"
    print(f"  {S.OK} Step 2: Fetched {len(prices)} coin prices in {fetch_time:.2f}s")

    # Step 4: Insert to DB
    start = time.time()
    inserted = db.insert_ticker(prices)
    insert_time = time.time() - start
    assert inserted == len(prices), (
        f"{S.FAILED}: Expected {len(prices)} inserts, got {inserted}"
    )
    print(f"  {S.OK} Step 3: Inserted {inserted} rows in {insert_time:.4f}s")

    # Step 5: Verify in DB
    final_count = db.get_row_count("market_ticker")
    assert final_count == initial_count + len(prices), (
        f"{S.FAILED}: Row count mismatch"
    )
    print(f"  {S.OK} Step 4: Verified in DB (total: {final_count} rows)")

    # Step 6: Query latest prices
    latest = db.get_latest_prices()
    print(f"\n  {S.DATA} Latest prices from DB:")
    for row in latest:
        symbol, price, volume, change, ts = row
        print(
            f"     {S.BULLET} {symbol}: ${float(price):,.2f} "
            f"(vol: ${float(volume):,.0f}, change: {float(change):.2f}%)"
        )

    db.disconnect()
    print(f"\n  {S.PASS}: End-to-end ticker pipeline works!")
    return True


def test_end_to_end_ohlc():
    """Test 4b: Full pipeline — fetch OHLC and insert to DB."""
    print(styled_header("TEST 4b: End-to-End OHLC Pipeline"))

    api = CoinGeckoClient()
    db = DatabaseManager()

    assert db.connect(), f"{S.FAILED}: Cannot connect to DB"
    print(f"  {S.OK} Step 1: DB connected")

    initial_count = db.get_row_count("market_ohlc")
    print(f"  {S.DATA} Initial OHLC row count: {initial_count}")

    # Fetch OHLC for Bitcoin
    ohlc = api.fetch_ohlc("bitcoin", days=1)
    assert len(ohlc) > 0, f"{S.FAILED}: No OHLC data fetched"
    print(f"  {S.OK} Step 2: Fetched {len(ohlc)} OHLC candles for Bitcoin")

    # Insert to DB
    inserted = db.insert_ohlc("bitcoin", ohlc)
    print(f"  {S.OK} Step 3: Inserted {inserted} OHLC rows")

    final_count = db.get_row_count("market_ohlc")
    print(f"  {S.DATA} Final OHLC row count: {final_count}")

    db.disconnect()
    print(f"  {S.PASS}: End-to-end OHLC pipeline works!")
    return True


def test_multi_cycle():
    """Test 4c: Multiple fetch-insert cycles (simulating streaming)."""
    print(styled_header("TEST 4c: Multi-Cycle Streaming Simulation (3 cycles)"))

    api = CoinGeckoClient()
    db = DatabaseManager()
    assert db.connect(), f"{S.FAILED}: Cannot connect to DB"

    initial_count = db.get_row_count("market_ticker")
    total_inserted = 0

    for cycle in range(1, 4):
        print(f"\n  {S.DIM}── Cycle {cycle}/3 ──{S.R}")
        prices = api.fetch_prices(["bitcoin", "ethereum"])
        if prices:
            inserted = db.insert_ticker(prices)
            total_inserted += inserted
            print(f"     {S.BULLET} Inserted {inserted} rows")
        else:
            print(f"     {S.WARN} No data in cycle {cycle}")

        if cycle < 3:
            print(f"     {S.WAIT} Waiting 10s...")
            time.sleep(10)

    final_count = db.get_row_count("market_ticker")
    print(f"\n  {S.DATA} Total inserted: {total_inserted} rows")
    print(f"  {S.DATA} DB count: {initial_count} -> {final_count}")

    assert total_inserted >= 4, (
        f"{S.FAILED}: Expected >=4 inserts, got {total_inserted}"
    )
    print(f"  {S.PASS}: Multi-cycle streaming works!")

    db.disconnect()
    return True


if __name__ == "__main__":
    print(styled_header("INTEGRATION TESTS (E2E Pipeline)"))
    results = []

    for name, test_fn in [
        ("E2E Ticker Pipeline", test_end_to_end_ticker),
        ("E2E OHLC Pipeline", test_end_to_end_ohlc),
        ("Multi-Cycle Streaming", test_multi_cycle),
    ]:
        try:
            results.append((name, test_fn()))
        except AssertionError as e:
            print(f"  {e}")
            results.append((name, False))
        except Exception as e:
            print(f"  {S.FAIL} Unexpected error in {name}: {type(e).__name__}: {e}")
            results.append((name, False))

    all_pass, summary = styled_summary(results)
    print(summary)
    sys.exit(0 if all_pass else 1)
