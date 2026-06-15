"""
Konfigurasi terpusat untuk Real-Time Financial Market BI Dashboard.
Semua parameter pipeline, API, dan database dikonfigurasi di sini.
"""

import os

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
DB_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "database": os.getenv("PG_DATABASE", "portofolio_db"),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", "postgres123"),
}

# Connection string untuk SQLAlchemy / Superset
DB_URI = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

# Whitelist tabel yang diizinkan untuk query dinamis (anti SQL injection)
VALID_TABLES = {"market_ticker", "market_ohlc"}

# Sumber data aktif (digunakan sebagai label di kolom 'source')
DATA_SOURCE = "coingecko"

# ============================================================
# COINGECKO API CONFIGURATION (Reverted from Binance due to ISP block)
# ============================================================
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Endpoint yang digunakan
COINGECKO_ENDPOINTS = {
    "simple_price": f"{COINGECKO_BASE_URL}/simple/price",
    "ohlc": f"{COINGECKO_BASE_URL}/coins/{{coin_id}}/ohlc",
}

# ============================================================
# COINS TO TRACK
# ============================================================
COINS = [
    "bitcoin",
    "ethereum",
    "solana",
    "ripple",
    "cardano",
    "dogecoin",
]

# Mapping dari CoinGecko ID ke simbol yang lebih singkat (untuk display)
COIN_SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "ripple": "XRP",
    "cardano": "ADA",
    "dogecoin": "DOGE",
}

# ============================================================
# STREAMING ENGINE CONFIGURATION
# ============================================================
# Interval fetch harga (detik) — CoinGecko free tier: max ~10-30 req/menit
PRICE_FETCH_INTERVAL = 60

# Interval fetch OHLC data (detik) — data OHLC tidak berubah per detik
OHLC_FETCH_INTERVAL = 300  # 5 menit

# OHLC timeframe: 1 = 24 jam terakhir (interval 30 menit)
OHLC_DAYS = 1

# ============================================================
# LOGGING
# ============================================================
LOG_FILE = "streaming.log"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
LOG_LEVEL = "INFO"
