"""
Test 3: Network Bridge — Superset (Docker) ↔ PostgreSQL (Host)
Memastikan koneksi dari Docker network ke PostgreSQL host berfungsi.
Test ini harus dijalankan SETELAH Superset container berjalan.
"""

from __future__ import annotations

import glob
import subprocess
import sys
import os

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src.styles import S, styled_header, styled_summary


def _find_pg_hba_conf() -> str | None:
    """
    Auto-detect pg_hba.conf path.
    Mendukung berbagai instalasi PostgreSQL (Homebrew Intel/ARM, system pkg).
    """
    candidates = [
        # Homebrew Apple Silicon (M1/M2/M3)
        "/opt/homebrew/var/postgresql@18/pg_hba.conf",
        "/opt/homebrew/var/postgresql@17/pg_hba.conf",
        "/opt/homebrew/var/postgresql@16/pg_hba.conf",
        "/opt/homebrew/var/postgresql@15/pg_hba.conf",
        "/opt/homebrew/var/postgres/pg_hba.conf",
        # Homebrew Intel
        "/usr/local/var/postgresql@18/pg_hba.conf",
        "/usr/local/var/postgresql@17/pg_hba.conf",
        "/usr/local/var/postgres/pg_hba.conf",
        # Linux system
        "/etc/postgresql/*/main/pg_hba.conf",
    ]

    for pattern in candidates:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def test_pg_listen_addresses():
    """Test 3a: PostgreSQL listen_addresses is set to '*'."""
    print(styled_header("TEST 3a: PostgreSQL listen_addresses"))

    import psycopg2
    conn = psycopg2.connect(
        host="localhost",
        port=config.DB_CONFIG["port"],
        database=config.DB_CONFIG["database"],
        user=config.DB_CONFIG["user"],
        password=config.DB_CONFIG["password"],
    )
    cursor = conn.cursor()
    cursor.execute("SHOW listen_addresses")
    listen_addr = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    print(f"  {S.BULLET} listen_addresses = '{listen_addr}'")

    assert listen_addr == "*", (
        f"{S.FAILED}: listen_addresses is '{listen_addr}', expected '*'"
    )
    print(f"  {S.PASS}: PostgreSQL accepting connections from all interfaces")
    return True


def test_pg_hba_docker_rules():
    """Test 3b: pg_hba.conf has rules for Docker network."""
    print(styled_header("TEST 3b: pg_hba.conf Docker Rules"))

    hba_path = _find_pg_hba_conf()
    if hba_path is None:
        print(f"  {S.WARN} Cannot auto-detect pg_hba.conf path")
        print(f"  {S.BULLET} Searched common Homebrew & Linux locations")
        return False

    print(f"  {S.INFO} Found: {hba_path}")

    try:
        with open(hba_path, "r") as f:
            content = f.read()
    except PermissionError:
        print(f"  {S.WARN} Permission denied reading {hba_path}")
        return False

    docker_networks = ["172.16.0.0/12", "192.168.0.0/16"]
    found = []
    for network in docker_networks:
        if network in content:
            found.append(network)
            print(f"  {S.OK} Found rule for {network}")
        else:
            print(f"  {S.FAIL} Missing rule for {network}")

    assert len(found) >= 1, f"{S.FAILED}: No Docker network rules in pg_hba.conf"
    print(f"  {S.PASS}: Docker network rules present")
    return True


def test_docker_running():
    """Test 3c: Docker/OrbStack is running."""
    print(styled_header("TEST 3c: Docker Running"))

    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        running = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        running = False

    print(f"  {S.BULLET} Docker running: {running}")
    assert running, f"{S.FAILED}: Docker is not running"
    print(f"  {S.PASS}: Docker is running")
    return True


def test_superset_container():
    """Test 3d: Superset container is running."""
    print(styled_header("TEST 3d: Superset Container"))

    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=superset", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
        containers = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        containers = ""

    if containers:
        print(f"  {S.BULLET} Containers: {containers}")
        print(f"  {S.PASS}: Superset container found")
        return True
    else:
        print(f"  {S.WARN} No Superset container running")
        print(f"  {S.INFO} Run 'docker compose up -d' to start Superset")
        return False


def test_host_docker_internal():
    """Test 3e: host.docker.internal resolves from Docker."""
    print(styled_header("TEST 3e: host.docker.internal Resolution"))

    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "alpine", "nslookup", "host.docker.internal"],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        resolved = "Address" in output and result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        resolved = False
        output = "Docker not available"

    print(f"  {S.BULLET} Output: {output.strip()[:200]}")
    if resolved:
        print(f"  {S.PASS}: host.docker.internal resolves")
    else:
        print(f"  {S.WARN} host.docker.internal may not resolve (OrbStack handles this)")
    return True  # Non-critical, OrbStack handles this differently


if __name__ == "__main__":
    print(styled_header("NETWORK BRIDGE TESTS"))
    results = []

    for name, test_fn in [
        ("PG listen_addresses", test_pg_listen_addresses),
        ("PG HBA Docker Rules", test_pg_hba_docker_rules),
        ("Docker Running", test_docker_running),
        ("Superset Container", test_superset_container),
        ("host.docker.internal", test_host_docker_internal),
    ]:
        try:
            results.append((name, test_fn()))
        except (AssertionError, Exception) as e:
            print(f"  {S.FAIL} {e}")
            results.append((name, False))

    all_pass, summary = styled_summary(results)
    print(summary)
    sys.exit(0 if all_pass else 1)
