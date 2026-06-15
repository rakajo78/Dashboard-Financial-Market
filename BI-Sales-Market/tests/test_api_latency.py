"""
Test 1: API Latency Test
Memastikan CoinGecko API merespons dalam waktu yang wajar
dan data yang dikembalikan valid (termasuk null-safe).
"""

import sys
import time
import os

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api_client import CoinGeckoClient
from src.styles import S, styled_header, styled_summary


def test_api_ping():
    """Test 1a: API Ping latency."""
    print(styled_header("TEST 1a: CoinGecko API Ping"))

    client = CoinGeckoClient()
    reachable, latency = client.ping()

    print(f"  {S.BULLET} Reachable: {reachable}")
    print(f"  {S.BULLET} Latency:   {latency:.3f}s")

    assert reachable, f"{S.FAILED}: API not reachable"
    assert latency < 2.0, f"{S.FAILED}: Latency {latency:.3f}s > 2s threshold"
    print(f"  {S.PASS}: API ping < 2s")
    return True


def test_price_fetch_latency():
    """Test 1b: Price fetch latency and data validation (null-safe)."""
    print(styled_header("TEST 1b: Price Fetch Latency & Data Validation"))

    client = CoinGeckoClient()

    start = time.time()
    prices = client.fetch_prices(["bitcoin", "ethereum"])
    latency = time.time() - start

    print(f"  {S.BULLET} Fetch latency: {latency:.3f}s")
    print(f"  {S.BULLET} Coins fetched: {len(prices)}")

    # Validate latency
    assert latency < 2.5, f"{S.FAILED}: Fetch latency {latency:.3f}s > 2.5s"
    print(f"  {S.PASS}: Fetch latency < 2.5s")

    # Validate data
    assert len(prices) >= 2, f"{S.FAILED}: Expected 2 coins, got {len(prices)}"
    print(f"  {S.PASS}: Got data for 2 coins")

    for p in prices:
        print(f"\n  {S.DATA} {S.BOLD}{p['symbol']}:{S.R}")
        print(f"     {S.BULLET} Price:      ${p['price_usd']:,.2f}")
        print(f"     {S.BULLET} Market Cap: ${p['market_cap']:,.0f}")
        print(f"     {S.BULLET} Volume 24h: ${p['volume_24h']:,.0f}")
        print(f"     {S.BULLET} Change 24h: {p['change_24h_pct']:.2f}%")

        # Null-safe checks: price_usd harus > 0 (bukan None atau 0)
        assert p["price_usd"] > 0, f"{S.FAILED}: Price is 0/null for {p['symbol']}"
        assert isinstance(p["price_usd"], (int, float)), (
            f"{S.FAILED}: price_usd is not numeric for {p['symbol']}"
        )
        assert "symbol" in p, f"{S.FAILED}: Missing 'symbol' key"
        assert "market_cap" in p, f"{S.FAILED}: Missing 'market_cap' key"

    print(f"\n  {S.PASS}: All data fields valid (null-safe)")
    return True


def test_ohlc_fetch():
    """Test 1c: OHLC data fetch and validation."""
    print(styled_header("TEST 1c: OHLC Fetch"))

    client = CoinGeckoClient()

    start = time.time()
    ohlc = client.fetch_ohlc("bitcoin", days=1)
    latency = time.time() - start

    print(f"  {S.BULLET} Fetch latency: {latency:.3f}s")
    print(f"  {S.BULLET} Candles:       {len(ohlc)}")

    assert latency < 2.5, f"{S.FAILED}: OHLC fetch latency {latency:.3f}s > 2.5s"
    print(f"  {S.PASS}: OHLC fetch latency < 2.5s")

    assert len(ohlc) > 0, f"{S.FAILED}: No OHLC data returned"
    print(f"  {S.PASS}: OHLC data received")

    # Validate structure: [timestamp, open, high, low, close]
    sample = ohlc[0]
    assert len(sample) == 5, f"{S.FAILED}: Expected 5 fields, got {len(sample)}"
    print(f"  {S.PASS}: OHLC structure valid [ts, O, H, L, C]")
    print(f"     {S.BULLET} Sample: ts={sample[0]}, O={sample[1]}, H={sample[2]}, L={sample[3]}, C={sample[4]}")

    return True


if __name__ == "__main__":
    print(styled_header("API LATENCY TESTS"))
    results = []

    for name, test_fn in [
        ("Ping", test_api_ping),
        ("Price Fetch", test_price_fetch_latency),
        ("OHLC Fetch", test_ohlc_fetch),
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
