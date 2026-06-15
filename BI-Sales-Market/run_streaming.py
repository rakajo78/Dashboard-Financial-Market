"""
Streaming Engine — Main pipeline yang mengalirkan data market ke PostgreSQL.

Menjalankan dua loop paralel:
  1. Price ticker fetch (setiap PRICE_FETCH_INTERVAL detik)
  2. OHLC/Klines data fetch (setiap OHLC_FETCH_INTERVAL detik)

Data source: CoinGecko Public API (BTC, ETH, SOL, XRP, ADA, DOGE)

Usage:
    python run_streaming.py
    Ctrl+C untuk stop (graceful shutdown)
"""

import logging
import signal
import sys
import threading
import time

from src import config
from src.api_client import CoinGeckoClient
from src.db_manager import DatabaseManager
from src.styles import S

# Setup logging — stdout + file
logging.basicConfig(
    format=config.LOG_FORMAT,
    level=config.LOG_LEVEL,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("StreamingEngine")


class StreamingEngine:
    """
    Real-time streaming pipeline:
    CoinGecko API → Python → PostgreSQL
    """

    def __init__(self):
        self.api = CoinGeckoClient()
        self.db = DatabaseManager()
        self._running = False
        self._ohlc_thread: threading.Thread | None = None
        self._stats = {
            "total_ticker_inserts": 0,
            "total_ohlc_inserts": 0,
            "fetch_errors": 0,
            "start_time": None,
        }

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------
    def start(self):
        """Start the streaming engine."""
        logger.info(S.DLINE)
        logger.info("%s Starting Real-Time Financial Market Streaming Engine", S.START)
        logger.info(S.DLINE)
        logger.info("%s Symbols: %s", S.INFO, ", ".join(config.COINS))
        logger.info("%s Price interval: %ds", S.INFO, config.PRICE_FETCH_INTERVAL)
        logger.info("%s OHLC interval: %ds", S.INFO, config.OHLC_FETCH_INTERVAL)
        logger.info("%s Data source: CoinGecko Public API", S.API)
        logger.info(S.DLINE)

        # Connect to database
        if not self.db.connect():
            logger.error("%s Cannot start — database connection failed", S.FAIL)
            sys.exit(1)

        # Check API connectivity
        reachable, latency = self.api.ping()
        if not reachable:
            logger.error("%s Cannot start — CoinGecko API unreachable", S.FAIL)
            sys.exit(1)
        logger.info("%s CoinGecko API OK (latency: %.2fs)", S.API, latency)

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._running = True
        self._stats["start_time"] = time.time()

        # Start OHLC fetcher in background thread
        self._ohlc_thread = threading.Thread(
            target=self._ohlc_loop, daemon=True, name="OHLC-Fetcher"
        )
        self._ohlc_thread.start()
        logger.info(
            "%s OHLC fetcher started (interval: %ds)",
            S.CANDLE, config.OHLC_FETCH_INTERVAL,
        )

        # Run main price ticker loop (blocking)
        self._price_loop()

    def stop(self):
        """Stop the streaming engine gracefully."""
        logger.info("")
        logger.info(S.DLINE)
        logger.info("%s Stopping Streaming Engine...", S.STOP)
        self._running = False

        # Print final statistics
        elapsed = time.time() - (self._stats["start_time"] or time.time())
        logger.info("%s Final Statistics:", S.CHART)
        logger.info("   %s Runtime: %.1f seconds", S.BULLET, elapsed)
        logger.info(
            "   %s Ticker rows inserted: %d",
            S.BULLET, self._stats["total_ticker_inserts"],
        )
        logger.info(
            "   %s OHLC rows inserted: %d",
            S.BULLET, self._stats["total_ohlc_inserts"],
        )
        logger.info(
            "   %s Fetch errors: %d",
            S.BULLET, self._stats["fetch_errors"],
        )

        # Show DB counts
        ticker_count = self.db.get_row_count("market_ticker")
        ohlc_count = self.db.get_row_count("market_ohlc")
        if ticker_count >= 0:
            logger.info(
                "   %s Total in market_ticker: %d rows", S.DB, ticker_count
            )
        if ohlc_count >= 0:
            logger.info(
                "   %s Total in market_ohlc: %d rows", S.DB, ohlc_count
            )

        self.db.disconnect()
        logger.info(S.DLINE)
        logger.info("%s Engine stopped. Goodbye!", S.PLUG)

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C and SIGTERM."""
        self.stop()
        sys.exit(0)

    # ----------------------------------------------------------
    # Main Loops
    # ----------------------------------------------------------
    def _price_loop(self):
        """Main loop: fetch prices and insert to DB every N seconds."""
        cycle = 0
        while self._running:
            cycle += 1
            try:
                logger.info(
                    "%s%s── Cycle %d ──%s", S.DIM, S.CYAN, cycle, S.R
                )

                # Fetch prices from CoinGecko
                ticker_data = self.api.fetch_prices()

                if ticker_data:
                    # Insert to PostgreSQL
                    inserted = self.db.insert_ticker(ticker_data)
                    self._stats["total_ticker_inserts"] += inserted
                else:
                    self._stats["fetch_errors"] += 1
                    logger.warning(
                        "%s No data fetched in cycle %d", S.WARN, cycle
                    )

                # Wait for next cycle
                if self._running:
                    time.sleep(config.PRICE_FETCH_INTERVAL)

            except Exception as e:
                self._stats["fetch_errors"] += 1
                logger.error(
                    "%s Error in price loop cycle %d: %s", S.FAIL, cycle, e
                )
                time.sleep(config.PRICE_FETCH_INTERVAL)

    def _ohlc_loop(self):
        """Background loop: fetch OHLC data every N seconds."""
        # Small delay to let price loop start first
        time.sleep(10)
        if not self._running:
            return
        self._fetch_all_ohlc()

        while self._running:
            time.sleep(config.OHLC_FETCH_INTERVAL)
            if self._running:
                self._fetch_all_ohlc()

    def _fetch_all_ohlc(self):
        """Fetch OHLC data for major coins."""
        ohlc_symbols = ["bitcoin", "ethereum"]
        logger.info(
            "%s Fetching OHLC data for %s...", S.CANDLE, ohlc_symbols
        )
        for symbol in ohlc_symbols:
            if not self._running:
                break
            try:
                display = config.COIN_SYMBOLS.get(symbol, symbol)
                ohlc_data = self.api.fetch_ohlc(symbol)
                if ohlc_data:
                    inserted = self.db.insert_ohlc(display, ohlc_data)
                    self._stats["total_ohlc_inserts"] += inserted
            except Exception as e:
                self._stats["fetch_errors"] += 1
                logger.error(
                    "%s OHLC fetch failed for %s: %s", S.FAIL, symbol, e
                )


# ==============================================================
# Entry Point
# ==============================================================
if __name__ == "__main__":
    engine = StreamingEngine()
    engine.start()
