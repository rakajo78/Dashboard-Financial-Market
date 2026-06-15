"""
Database Manager — Mengelola koneksi dan operasi ke PostgreSQL.
Mendukung insert ticker dan OHLC data dengan:
  - Retry logic pada koneksi
  - Batch insert untuk performa tinggi
  - Null-safe tanpa mutasi input
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from src import config
from src.api_client import _safe_float
from src.styles import S

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connection and data operations."""

    def __init__(self):
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.cursor: Optional[psycopg2.extensions.cursor] = None

    # ----------------------------------------------------------
    # Connection Management
    # ----------------------------------------------------------
    def connect(self, max_retries: int = 3) -> bool:
        """
        Establish connection to PostgreSQL with retry logic.
        Returns True if successful.
        """
        for attempt in range(1, max_retries + 1):
            try:
                self.conn = psycopg2.connect(
                    host=config.DB_CONFIG["host"],
                    port=config.DB_CONFIG["port"],
                    database=config.DB_CONFIG["database"],
                    user=config.DB_CONFIG["user"],
                    password=config.DB_CONFIG["password"],
                )
                self.conn.autocommit = True
                self.cursor = self.conn.cursor()
                logger.info(
                    "%s Connected to PostgreSQL: %s@%s:%s/%s",
                    S.OK,
                    config.DB_CONFIG["user"],
                    config.DB_CONFIG["host"],
                    config.DB_CONFIG["port"],
                    config.DB_CONFIG["database"],
                )
                return True
            except psycopg2.Error as e:
                logger.error(
                    "%s DB connect attempt %d/%d failed: %s",
                    S.FAIL, attempt, max_retries, e,
                )
                if attempt < max_retries:
                    wait = 2 * attempt
                    logger.info(
                        "%s Retrying in %ds...", S.WAIT, wait
                    )
                    time.sleep(wait)
        return False

    def disconnect(self):
        """Close the database connection gracefully."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("%s Disconnected from PostgreSQL", S.PLUG)

    def _ensure_connection(self) -> bool:
        """Ensure the connection is alive, reconnect if needed."""
        try:
            if self.conn is None or self.conn.closed:
                logger.warning("%s Connection lost, reconnecting...", S.WARN)
                return self.connect()
            # Ping test
            self.cursor.execute("SELECT 1")
            return True
        except psycopg2.Error:
            logger.warning("%s Connection stale, reconnecting...", S.WARN)
            return self.connect()

    # ----------------------------------------------------------
    # Insert Operations
    # ----------------------------------------------------------
    def insert_ticker(self, ticker_data: list[dict]) -> int:
        """
        Insert ticker data into market_ticker table.
        Creates copies of input dicts to avoid mutation side effects.

        Args:
            ticker_data: List of dicts with keys:
                symbol, price_usd, market_cap, volume_24h, change_24h_pct

        Returns:
            Number of rows inserted.
        """
        if not self._ensure_connection():
            return 0

        sql = """
            INSERT INTO market_ticker
                (symbol, price_usd, market_cap, volume_24h, change_24h_pct, fetched_at, source)
            VALUES
                (%(symbol)s, %(price_usd)s, %(market_cap)s, %(volume_24h)s,
                 %(change_24h_pct)s, %(fetched_at)s, %(source)s)
        """

        now = datetime.now(timezone.utc)

        # Build insert rows WITHOUT mutating the original dicts
        # Sanitize semua nilai numerik agar tidak ada NULL masuk ke DB
        rows_to_insert = []
        for row in ticker_data:
            enriched = {
                "symbol": row.get("symbol", "UNKNOWN"),
                "price_usd": _safe_float(row.get("price_usd")),
                "market_cap": _safe_float(row.get("market_cap")),
                "volume_24h": _safe_float(row.get("volume_24h")),
                "change_24h_pct": _safe_float(row.get("change_24h_pct")),
                "fetched_at": now,
                "source": config.DATA_SOURCE,
            }
            rows_to_insert.append(enriched)

        try:
            psycopg2.extras.execute_batch(self.cursor, sql, rows_to_insert)
            rows_inserted = len(rows_to_insert)
            logger.info(
                "%s Inserted %d ticker rows at %s",
                S.DATA, rows_inserted, now.strftime("%H:%M:%S UTC"),
            )
            return rows_inserted

        except psycopg2.Error as e:
            logger.error("%s Insert ticker failed: %s", S.FAIL, e)
            return 0

    def insert_ohlc(self, symbol: str, ohlc_data: list[list]) -> int:
        """
        Insert OHLC data into market_ohlc table.
        Uses ON CONFLICT DO NOTHING to avoid duplicate timestamps.

        Args:
            symbol: Coin symbol (e.g. 'BTC')
            ohlc_data: List of [timestamp_ms, open, high, low, close]

        Returns:
            Number of rows inserted.
        """
        if not self._ensure_connection():
            return 0

        sql = """
            INSERT INTO market_ohlc
                (symbol, timestamp, open_price, high_price, low_price, close_price, fetched_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, timestamp) DO NOTHING
        """

        now = datetime.now(timezone.utc)
        rows_inserted = 0

        try:
            for item in ohlc_data:
                ts = datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc)
                # Sanitize OHLC values — ganti None dengan 0.0
                open_p = _safe_float(item[1])
                high_p = _safe_float(item[2])
                low_p = _safe_float(item[3])
                close_p = _safe_float(item[4])
                self.cursor.execute(sql, (
                    symbol, ts, open_p, high_p, low_p, close_p, now
                ))
                rows_inserted += self.cursor.rowcount

            logger.info(
                "%s Inserted %d OHLC rows for %s",
                S.CANDLE, rows_inserted, symbol,
            )
            return rows_inserted

        except psycopg2.Error as e:
            logger.error("%s Insert OHLC failed for %s: %s", S.FAIL, symbol, e)
            return 0

    # ----------------------------------------------------------
    # Query Operations (for testing/validation)
    # ----------------------------------------------------------
    def get_row_count(self, table: str) -> int:
        """Get total row count for a table (whitelist-protected)."""
        if table not in config.VALID_TABLES:
            logger.error("%s Invalid table name: %s", S.FAIL, table)
            return -1
        if not self._ensure_connection():
            return -1
        try:
            # Aman karena table sudah divalidasi terhadap whitelist
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            return self.cursor.fetchone()[0]
        except psycopg2.Error as e:
            logger.error("%s Count query failed: %s", S.FAIL, e)
            return -1

    def get_latest_prices(self) -> list[tuple]:
        """Get the latest price for each symbol."""
        if not self._ensure_connection():
            return []
        try:
            self.cursor.execute("""
                SELECT DISTINCT ON (symbol)
                    symbol, price_usd, volume_24h, change_24h_pct, fetched_at
                FROM market_ticker
                ORDER BY symbol, fetched_at DESC
            """)
            return self.cursor.fetchall()
        except psycopg2.Error as e:
            logger.error("%s Latest prices query failed: %s", S.FAIL, e)
            return []
