"""
Test 2: Database Connection & Insert Rate Test
Memastikan PostgreSQL mampu menerima insert berkecepatan tinggi
dan data konsisten.
"""

import sys
import time
import os

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db_manager import DatabaseManager
from src.styles import S, styled_header, styled_summary


def test_db_connection():
    """Test 2a: Database connection with retry."""
    print(styled_header("TEST 2a: Database Connection"))

    db = DatabaseManager()

    start = time.time()
    connected = db.connect()
    latency = time.time() - start

    print(f"  {S.BULLET} Connected: {connected}")
    print(f"  {S.BULLET} Latency:   {latency:.3f}s")

    assert connected, f"{S.FAILED}: Cannot connect to PostgreSQL"
    print(f"  {S.PASS}: Connected to PostgreSQL")

    db.disconnect()
    return True


def test_insert_rate():
    """Test 2b: High-frequency insert rate."""
    print(styled_header("TEST 2b: Insert Rate Test"))

    db = DatabaseManager()
    assert db.connect(), f"{S.FAILED}: Cannot connect to DB"

    # Get initial count
    initial_count = db.get_row_count("market_ticker")
    print(f"  {S.BULLET} Initial row count: {initial_count}")

    # Insert 50 rows rapidly
    num_inserts = 50
    test_data = [
        {
            "symbol": "test_coin",
            "price_usd": 100.0 + i,
            "market_cap": 1000000.0,
            "volume_24h": 50000.0,
            "change_24h_pct": 1.5,
        }
        for i in range(num_inserts)
    ]

    start = time.time()
    for row in test_data:
        db.insert_ticker([row])
    elapsed = time.time() - start

    # Check count
    final_count = db.get_row_count("market_ticker")
    inserted = final_count - initial_count

    rate = num_inserts / elapsed if elapsed > 0 else 0
    print(f"  {S.BULLET} Inserted:  {inserted} rows")
    print(f"  {S.BULLET} Time:      {elapsed:.3f}s")
    print(f"  {S.BULLET} Rate:      {rate:.1f} inserts/sec")

    assert inserted == num_inserts, (
        f"{S.FAILED}: Expected {num_inserts}, inserted {inserted}"
    )
    print(f"  {S.PASS}: All rows inserted correctly")

    assert rate > 10, f"{S.FAILED}: Insert rate {rate:.1f}/s too slow (need >10/s)"
    print(f"  {S.PASS}: Insert rate > 10/sec")

    # Cleanup test data
    db.cursor.execute("DELETE FROM market_ticker WHERE symbol = 'test_coin'")
    print(f"  {S.CLEAN} Cleaned up test data")

    db.disconnect()
    return True


def test_data_consistency():
    """Test 2c: Data consistency after batch insert (no mutation check)."""
    print(styled_header("TEST 2c: Data Consistency"))

    db = DatabaseManager()
    assert db.connect(), f"{S.FAILED}: Cannot connect to DB"

    # Insert a batch of known data
    batch = [
        {"symbol": "consistency_test", "price_usd": 42000.50,
         "market_cap": 800000000000.0, "volume_24h": 30000000000.0,
         "change_24h_pct": 2.5},
        {"symbol": "consistency_test", "price_usd": 42100.75,
         "market_cap": 810000000000.0, "volume_24h": 31000000000.0,
         "change_24h_pct": 2.7},
    ]

    # Verify no mutation: original dicts should NOT have 'fetched_at' after insert
    inserted = db.insert_ticker(batch)
    assert inserted == 2, f"{S.FAILED}: Expected 2 inserts, got {inserted}"
    assert "fetched_at" not in batch[0], (
        f"{S.FAILED}: insert_ticker mutated input dict (added 'fetched_at')"
    )
    print(f"  {S.PASS}: No input mutation detected")

    # Verify data in DB
    db.cursor.execute(
        "SELECT price_usd, market_cap FROM market_ticker "
        "WHERE symbol = 'consistency_test' ORDER BY id DESC LIMIT 2"
    )
    rows = db.cursor.fetchall()

    assert len(rows) == 2, f"{S.FAILED}: Expected 2 rows, got {len(rows)}"
    print(f"  {S.BULLET} Row 1: price={rows[0][0]}, market_cap={rows[0][1]}")
    print(f"  {S.BULLET} Row 2: price={rows[1][0]}, market_cap={rows[1][1]}")
    print(f"  {S.PASS}: Data consistency verified")

    # Cleanup
    db.cursor.execute("DELETE FROM market_ticker WHERE symbol = 'consistency_test'")
    print(f"  {S.CLEAN} Cleaned up test data")

    db.disconnect()
    return True


if __name__ == "__main__":
    print(styled_header("DATABASE INSERT TESTS"))
    results = []

    for name, test_fn in [
        ("Connection", test_db_connection),
        ("Insert Rate", test_insert_rate),
        ("Data Consistency", test_data_consistency),
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
