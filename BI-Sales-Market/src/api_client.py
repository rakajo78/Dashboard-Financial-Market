"""
CoinGecko API Client — Mengambil data harga dan OHLC (Klines).
Dilengkapi retry logic, null-safe extraction, dan thread-safe rate limiting.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import requests

from src import config
from src.styles import S

logger = logging.getLogger(__name__)


def _safe_float(value, default: float = 0.0) -> float:
    """
    Convert value to float safely.
    Handles None, missing keys, dan tipe data yang tidak bisa di-cast.
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class CoinGeckoClient:
    """Client for fetching cryptocurrency data from CoinGecko Public API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "BI-Sales-Market-Dashboard/1.0",
        })
        self._last_request_time = 0.0
        self._min_interval = 2.0  # CoinGecko rate limit
        self._lock = threading.Lock()  # Thread-safe rate limiting

    def _rate_limit(self):
        """Enforce minimum interval between API requests (thread-safe)."""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_interval:
                wait = self._min_interval - elapsed
                time.sleep(wait)
            self._last_request_time = time.time()

    def _request(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[dict | list]:
        """Make an HTTP GET request with retry logic."""
        for attempt in range(1, max_retries + 1):
            self._rate_limit()
            try:
                start = time.time()
                response = self.session.get(url, params=params, timeout=10)
                latency = time.time() - start

                if response.status_code == 200:
                    logger.debug(
                        "%s API OK [%.2fs]: %s", S.OK, latency, url
                    )
                    return response.json()

                elif response.status_code == 429:
                    # Exponential backoff on rate limit
                    wait = 60 * attempt
                    logger.warning(
                        "%s Rate limited (429). Backoff %ds — retry %d/%d",
                        S.WAIT, wait, attempt, max_retries,
                    )
                    time.sleep(wait)
                    continue

                else:
                    logger.error(
                        "%s API error %d: %s",
                        S.FAIL, response.status_code, response.text[:200],
                    )

            except requests.exceptions.RequestException as e:
                logger.error("%s Request failed: %s", S.FAIL, e)

            if attempt < max_retries:
                time.sleep(10 * attempt)

        logger.error(
            "%s All %d attempts failed for: %s", S.FAIL, max_retries, url
        )
        return None

    def fetch_prices(self, coins: list[str] = None) -> list[dict]:
        """Fetch current prices with null-safe value extraction."""
        coins = coins or config.COINS

        params = {
            "ids": ",".join(coins),
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
        }

        data = self._request(config.COINGECKO_ENDPOINTS["simple_price"], params=params)
        if data is None:
            return []

        result = []
        for coin_id, metrics in data.items():
            if not isinstance(metrics, dict):
                logger.warning(
                    "%s Unexpected data format for %s, skipping", S.WARN, coin_id
                )
                continue

            display_symbol = config.COIN_SYMBOLS.get(coin_id, coin_id.upper())
            result.append({
                "symbol": display_symbol,
                "price_usd": _safe_float(metrics.get("usd")),
                "market_cap": _safe_float(metrics.get("usd_market_cap")),
                "volume_24h": _safe_float(metrics.get("usd_24h_vol")),
                "change_24h_pct": _safe_float(metrics.get("usd_24h_change")),
            })

        if result:
            logger.info(
                "%s Fetched prices for %d coins: %s",
                S.DATA, len(result),
                ", ".join(f"{r['symbol']}=${r['price_usd']:,.2f}" for r in result),
            )
        return result

    def fetch_ohlc(self, coin_id: str, days: int = None) -> list[list]:
        """Fetch OHLC data with validation."""
        days = days or config.OHLC_DAYS
        url = config.COINGECKO_ENDPOINTS["ohlc"].format(coin_id=coin_id)
        params = {"vs_currency": "usd", "days": days}

        data = self._request(url, params=params)
        if data:
            # Filter out malformed candles (must have exactly 5 elements)
            valid = []
            skipped = 0
            for c in data:
                if not isinstance(c, list) or len(c) != 5:
                    skipped += 1
                    continue
                # Sanitize: ganti None di dalam candle dengan 0.0
                # Format: [timestamp_ms, open, high, low, close]
                sanitized = [
                    c[0],  # timestamp — harus tetap angka asli
                    _safe_float(c[1]),
                    _safe_float(c[2]),
                    _safe_float(c[3]),
                    _safe_float(c[4]),
                ]
                valid.append(sanitized)

            if skipped > 0:
                logger.warning(
                    "%s Skipped %d malformed OHLC candles for %s",
                    S.WARN, skipped, coin_id,
                )
            logger.info(
                "%s Fetched %d OHLC candles for %s",
                S.CANDLE, len(valid), coin_id,
            )
            return valid
        return []

    def ping(self) -> tuple[bool, float]:
        """Ping API to check reachability."""
        start = time.time()
        try:
            response = self.session.get(
                "https://api.coingecko.com/api/v3/ping", timeout=5
            )
            # 200 OK or 429 Too Many Requests both mean the server is reachable
            is_reachable = response.status_code in (200, 429)
            if response.status_code == 429:
                logger.warning(
                    "%s Ping returned 429 Rate Limited, but API is reachable.",
                    S.WAIT,
                )
            return is_reachable, time.time() - start
        except requests.exceptions.RequestException:
            return False, time.time() - start
