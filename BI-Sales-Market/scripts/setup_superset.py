"""
Superset Setup Script — Menambahkan database connection dan membuat charts/dashboard
via Superset REST API.

Usage:
    python setup_superset.py
"""

import json
import sys
import time
import requests

SUPERSET_URL = "http://localhost:8088"


class SupersetSetup:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.csrf_token = None
        self.headers = {}

    def login(self, username="admin", password="admin123"):
        """Login to Superset and get JWT token."""
        # Try known usernames and passwords
        credentials = [
            (username, password),
            ("jonatansihombing", password),
            ("admin", "admin")
        ]
        
        for user, pwd in credentials:
            print(f"  Trying login with user: '{user}'")
            resp = self.session.post(
                f"{SUPERSET_URL}/api/v1/security/login",
                json={
                    "username": user,
                    "password": pwd,
                    "provider": "db",
                    "refresh": True,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
                print(f"  ✅ Logged in as '{user}'")
                
                # Get CSRF token
                csrf_resp = self.session.get(
                    f"{SUPERSET_URL}/api/v1/security/csrf_token/",
                    headers=self.headers,
                )
                if csrf_resp.status_code == 200:
                    self.csrf_token = csrf_resp.json().get("result")
                    self.headers["X-CSRFToken"] = self.csrf_token
                    self.headers["Referer"] = SUPERSET_URL
                
                return True
            else:
                print(f"    ❌ Failed (HTTP {resp.status_code})")
        
        print(f"  ❌ All login attempts failed")
        return False

    def add_database(self):
        """Add PostgreSQL database connection to Superset."""
        print("\n📦 Adding Database Connection...")
        
        # Check if database already exists
        resp = self.session.get(
            f"{SUPERSET_URL}/api/v1/database/",
            headers=self.headers,
        )
        if resp.status_code == 200:
            databases = resp.json().get("result", [])
            for db in databases:
                if db.get("database_name") == "Financial Market DB":
                    print(f"  ✅ Database 'Financial Market DB' already exists (id={db['id']})")
                    return db["id"]

        # Create new database connection
        db_payload = {
            "database_name": "Financial Market DB",
            "sqlalchemy_uri": "postgresql://postgres:postgres123@host.docker.internal:5432/portofolio_db",
            "expose_in_sqllab": True,
            "allow_run_async": True,
            "allow_ctas": False,
            "allow_cvas": False,
            "allow_dml": False,
            "extra": json.dumps({
                "metadata_params": {},
                "engine_params": {},
                "metadata_cache_timeout": {},
                "schemas_allowed_for_file_upload": []
            }),
        }

        resp = self.session.post(
            f"{SUPERSET_URL}/api/v1/database/",
            headers=self.headers,
            json=db_payload,
        )

        if resp.status_code in (200, 201):
            db_id = resp.json().get("id")
            print(f"  ✅ Database added successfully (id={db_id})")
            return db_id
        else:
            print(f"  ❌ Failed to add database: {resp.status_code}")
            print(f"     {resp.text[:500]}")
            return None

    def create_dataset(self, db_id, table_name, display_name=None):
        """Create a dataset (virtual table) from a database table."""
        display_name = display_name or table_name
        print(f"\n📊 Creating dataset: {display_name}...")
        
        # Check if exists
        resp = self.session.get(
            f"{SUPERSET_URL}/api/v1/dataset/",
            headers=self.headers,
            params={"q": json.dumps({"filters": [{"col": "table_name", "opr": "eq", "value": table_name}]})},
        )
        if resp.status_code == 200:
            datasets = resp.json().get("result", [])
            for ds in datasets:
                if ds.get("table_name") == table_name:
                    print(f"  ✅ Dataset '{table_name}' already exists (id={ds['id']})")
                    return ds["id"]

        payload = {
            "database": db_id,
            "table_name": table_name,
            "schema": "public",
        }

        resp = self.session.post(
            f"{SUPERSET_URL}/api/v1/dataset/",
            headers=self.headers,
            json=payload,
        )

        if resp.status_code in (200, 201):
            ds_id = resp.json().get("id")
            print(f"  ✅ Dataset created (id={ds_id})")
            return ds_id
        else:
            print(f"  ❌ Failed: {resp.status_code} - {resp.text[:300]}")
            return None

    def create_chart(self, datasource_id, chart_name, viz_type, query_context, **kwargs):
        """Create a chart in Superset."""
        print(f"\n📈 Creating chart: {chart_name}...")

        payload = {
            "slice_name": chart_name,
            "viz_type": viz_type,
            "datasource_id": datasource_id,
            "datasource_type": "table",
            "params": json.dumps(query_context),
            **kwargs,
        }

        resp = self.session.post(
            f"{SUPERSET_URL}/api/v1/chart/",
            headers=self.headers,
            json=payload,
        )

        if resp.status_code in (200, 201):
            chart_id = resp.json().get("id")
            print(f"  ✅ Chart created (id={chart_id})")
            return chart_id
        else:
            print(f"  ❌ Failed: {resp.status_code} - {resp.text[:300]}")
            return None

    def create_dashboard(self, title, chart_ids):
        """Create a dashboard with the specified charts."""
        print(f"\n🖥️  Creating dashboard: {title}...")

        # Build position JSON for the dashboard layout
        position_json = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": [],
                "parents": ["ROOT_ID"],
            },
            "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": title}},
        }

        # Add rows for each chart
        for i, chart_id in enumerate(chart_ids):
            if chart_id is None:
                continue
            row_id = f"ROW-{i}"
            chart_component_id = f"CHART-{chart_id}"

            position_json["GRID_ID"]["children"].append(row_id)
            position_json[row_id] = {
                "type": "ROW",
                "id": row_id,
                "children": [chart_component_id],
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            position_json[chart_component_id] = {
                "type": "CHART",
                "id": chart_component_id,
                "children": [],
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "meta": {
                    "width": 12,
                    "height": 50,
                    "chartId": chart_id,
                    "sliceName": f"Chart {chart_id}",
                },
            }

        payload = {
            "dashboard_title": title,
            "position_json": json.dumps(position_json),
            "published": True,
            "slug": "financial-market-realtime",
        }

        resp = self.session.post(
            f"{SUPERSET_URL}/api/v1/dashboard/",
            headers=self.headers,
            json=payload,
        )

        if resp.status_code in (200, 201):
            dash_id = resp.json().get("id")
            print(f"  ✅ Dashboard created (id={dash_id})")
            print(f"  🔗 URL: {SUPERSET_URL}/superset/dashboard/{dash_id}/")
            return dash_id
        else:
            print(f"  ❌ Failed: {resp.status_code} - {resp.text[:300]}")
            return None

    def setup_all(self):
        """Run the full Superset setup."""
        print("=" * 60)
        print("🔧 Setting up Apache Superset Dashboard")
        print("=" * 60)

        # Step 1: Login
        print("\n🔐 Logging in...")
        if not self.login():
            print("💀 Cannot proceed without login")
            sys.exit(1)

        # Step 2: Add database
        db_id = self.add_database()
        if not db_id:
            print("💀 Cannot proceed without database connection")
            sys.exit(1)

        # Step 3: Create datasets
        ticker_ds_id = self.create_dataset(db_id, "market_ticker", "Market Ticker")
        ohlc_ds_id = self.create_dataset(db_id, "market_ohlc", "Market OHLC")
        joined_ds_id = self.create_dataset(db_id, "market_joined_view", "Market Overview")

        if not ticker_ds_id or not ohlc_ds_id or not joined_ds_id:
            print("💀 Cannot proceed without datasets")
            sys.exit(1)

        # Step 4: Create charts
        chart_ids = []

        # Chart 1: Real-Time Price Line Chart (dari market_ticker)
        chart_ids.append(self.create_chart(
            ticker_ds_id,
            "📈 Real-Time Crypto Prices",
            "echarts_timeseries_line",
            {
                "datasource": f"{ticker_ds_id}__table",
                "viz_type": "echarts_timeseries_line",
                "x_axis": "fetched_at",
                "time_grain_sqla": "PT1M",
                "metrics": [{"label": "price_usd", "expressionType": "SIMPLE", "column": {"column_name": "price_usd"}, "aggregate": "AVG"}],
                "groupby": ["symbol"],
                "row_limit": 10000,
                "time_range": "Last hour",
                "extra_form_data": {},
            }
        ))

        # Chart 2: OHLC Close Price Trend (dari market_ohlc)
        chart_ids.append(self.create_chart(
            ohlc_ds_id,
            "🕯️ Market OHLC Trend (Close Price)",
            "echarts_timeseries_line",
            {
                "datasource": f"{ohlc_ds_id}__table",
                "viz_type": "echarts_timeseries_line",
                "x_axis": "timestamp",
                "time_grain_sqla": "PT15M",
                "metrics": [{"label": "close_price", "expressionType": "SIMPLE", "column": {"column_name": "close_price"}, "aggregate": "AVG"}],
                "groupby": ["symbol"],
                "row_limit": 1000,
                "time_range": "Last 24 hours",
                "extra_form_data": {},
            }
        ))

        # Chart 3: Joined Market Overview (dari market_joined_view)
        chart_ids.append(self.create_chart(
            joined_ds_id,
            "💹 Comprehensive Market Data",
            "table",
            {
                "datasource": f"{joined_ds_id}__table",
                "viz_type": "table",
                "query_mode": "raw",
                "columns": ["time", "symbol", "price_usd", "open_price", "high_price", "low_price", "close_price", "volume_24h", "change_24h_pct"],
                "metrics": [],
                "order_by_cols": [json.dumps(["time", False])],
                "row_limit": 100,
                "time_range": "Last hour",
                "adhoc_filters": [],
            }
        ))

        # Step 5: Create dashboard
        if any(chart_ids):
            valid_chart_ids = [c for c in chart_ids if c is not None]
            dash_id = self.create_dashboard(
                "🏦 Real-Time Financial Market Dashboard",
                valid_chart_ids,
            )
        else:
            print("⚠️  No charts created, skipping dashboard")

        # Summary
        print("\n" + "=" * 60)
        print("📋 SETUP SUMMARY")
        print("=" * 60)
        print(f"  Database ID:  {db_id}")
        print(f"  Datasets:     market_ticker (id={ticker_ds_id}), market_ohlc (id={ohlc_ds_id}), market_joined_view (id={joined_ds_id})")
        print(f"  Charts:       {len([c for c in chart_ids if c])} created")
        print(f"  Dashboard:    {SUPERSET_URL}/superset/dashboard/financial-market-realtime/")
        print(f"\n  🔐 Login: http://localhost:8088/login/")
        print(f"     Username: admin")
        print("=" * 60)


if __name__ == "__main__":
    setup = SupersetSetup()
    setup.setup_all()
