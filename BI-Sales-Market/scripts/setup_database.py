"""
Setup Database — Script untuk membuat database dan tabel dari awal.
Jalankan sekali saat pertama kali setup proyek.

Usage:
    python setup_database.py
"""

import logging
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg2
from src import config

logging.basicConfig(format=config.LOG_FORMAT, level=config.LOG_LEVEL)
logger = logging.getLogger("SetupDB")


def create_database():
    """Create the portofolio_db database if it doesn't exist."""
    try:
        # Connect to default 'postgres' database first
        conn = psycopg2.connect(
            host=config.DB_CONFIG["host"],
            port=config.DB_CONFIG["port"],
            database="postgres",
            user=config.DB_CONFIG["user"],
            password=config.DB_CONFIG["password"],
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (config.DB_CONFIG["database"],),
        )
        if cursor.fetchone():
            logger.info("✅ Database '%s' already exists", config.DB_CONFIG["database"])
        else:
            cursor.execute(f"CREATE DATABASE {config.DB_CONFIG['database']}")
            logger.info("✅ Created database '%s'", config.DB_CONFIG["database"])

        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        logger.error("❌ Failed to create database: %s", e)
        return False


def create_tables():
    """Create tables and indexes in portofolio_db."""
    try:
        conn = psycopg2.connect(
            host=config.DB_CONFIG["host"],
            port=config.DB_CONFIG["port"],
            database=config.DB_CONFIG["database"],
            user=config.DB_CONFIG["user"],
            password=config.DB_CONFIG["password"],
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Create market_ticker table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_ticker (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                price_usd NUMERIC(20, 8) NOT NULL DEFAULT 0,
                market_cap NUMERIC(25, 2) NOT NULL DEFAULT 0,
                volume_24h NUMERIC(25, 2) NOT NULL DEFAULT 0,
                change_24h_pct NUMERIC(10, 6) NOT NULL DEFAULT 0,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                source VARCHAR(50) DEFAULT 'coingecko'
            );
        """)
        logger.info("✅ Table 'market_ticker' ready")

        # Create indexes for market_ticker
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_symbol_time
            ON market_ticker(symbol, fetched_at DESC);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_time
            ON market_ticker(fetched_at DESC);
        """)
        logger.info("✅ Indexes for 'market_ticker' ready")

        # Create market_ohlc table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_ohlc (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                open_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
                high_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
                low_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
                close_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT uq_ohlc_symbol_timestamp UNIQUE (symbol, timestamp)
            );
        """)
        logger.info("✅ Table 'market_ohlc' ready")

        # Create indexes for market_ohlc
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_time
            ON market_ohlc(symbol, timestamp DESC);
        """)
        logger.info("✅ Indexes for 'market_ohlc' ready")

        # Create market_joined_view with COALESCE to eliminate NULLs
        # LEFT JOIN bisa menghasilkan NULL saat tidak ada OHLC match,
        # COALESCE memastikan Superset selalu menerima angka valid.
        cursor.execute("""
            CREATE OR REPLACE VIEW market_joined_view AS
            SELECT 
                t.symbol,
                t.fetched_at AS time,
                t.price_usd,
                COALESCE(t.volume_24h, 0) AS volume_24h,
                COALESCE(t.change_24h_pct, 0) AS change_24h_pct,
                COALESCE(o.open_price, 0) AS open_price,
                COALESCE(o.high_price, 0) AS high_price,
                COALESCE(o.low_price, 0) AS low_price,
                COALESCE(o.close_price, 0) AS close_price
            FROM market_ticker t
            LEFT JOIN market_ohlc o ON t.symbol = o.symbol 
                AND o.timestamp = (
                    SELECT MAX(timestamp) 
                    FROM market_ohlc 
                    WHERE symbol = t.symbol AND timestamp <= t.fetched_at
                );
        """)
        logger.info("✅ View 'market_joined_view' ready")

        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        logger.error("❌ Failed to create tables: %s", e)
        return False


def verify_setup():
    """Verify database setup by checking tables exist."""
    try:
        conn = psycopg2.connect(
            host=config.DB_CONFIG["host"],
            port=config.DB_CONFIG["port"],
            database=config.DB_CONFIG["database"],
            user=config.DB_CONFIG["user"],
            password=config.DB_CONFIG["password"],
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]

        logger.info("📋 Tables/Views in '%s': %s", config.DB_CONFIG["database"], tables)

        expected = {"market_ticker", "market_ohlc", "market_joined_view"}
        if expected.issubset(set(tables)):
            logger.info("✅ All required tables exist!")
        else:
            missing = expected - set(tables)
            logger.error("❌ Missing tables: %s", missing)

        cursor.close()
        conn.close()
        return expected.issubset(set(tables))
    except psycopg2.Error as e:
        logger.error("❌ Verification failed: %s", e)
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🔧 Setting up Real-Time Financial Market Database")
    logger.info("=" * 60)

    if not create_database():
        sys.exit(1)

    if not create_tables():
        sys.exit(1)

    if verify_setup():
        logger.info("=" * 60)
        logger.info("🎉 Database setup complete!")
        logger.info("=" * 60)
    else:
        logger.error("Setup verification failed")
        sys.exit(1)
