"""
Terminal Styling — ANSI colors dan Unicode symbols untuk output modern.
Menggantikan emoji yang tidak konsisten di semua terminal.

Usage:
    from src.styles import S
    print(f"{S.OK} Connected to database")
    print(f"{S.FAIL} Connection failed")
"""

from __future__ import annotations

import os

# ============================================================
# ANSI Color Codes
# ============================================================
# Auto-detect: disable colors jika terminal tidak mendukung
_NO_COLOR = os.getenv("NO_COLOR") is not None or not hasattr(os.sys.stdout, "isatty")

if _NO_COLOR:
    _RESET = ""
    _BOLD = ""
    _DIM = ""
    _GREEN = ""
    _RED = ""
    _YELLOW = ""
    _BLUE = ""
    _CYAN = ""
    _MAGENTA = ""
    _WHITE = ""
    _BG_GREEN = ""
    _BG_RED = ""
    _BG_YELLOW = ""
    _BG_BLUE = ""
else:
    _RESET = "\033[0m"
    _BOLD = "\033[1m"
    _DIM = "\033[2m"
    _GREEN = "\033[38;5;114m"      # Soft green
    _RED = "\033[38;5;204m"        # Soft red/pink
    _YELLOW = "\033[38;5;221m"     # Warm yellow
    _BLUE = "\033[38;5;75m"        # Sky blue
    _CYAN = "\033[38;5;80m"        # Teal cyan
    _MAGENTA = "\033[38;5;183m"    # Soft purple
    _WHITE = "\033[38;5;252m"      # Off-white
    _BG_GREEN = "\033[48;5;22m"    # Dark green bg
    _BG_RED = "\033[48;5;52m"      # Dark red bg
    _BG_YELLOW = "\033[48;5;58m"   # Dark yellow bg
    _BG_BLUE = "\033[48;5;17m"     # Dark blue bg


class S:
    """
    Styled symbols for terminal output.
    Menggunakan Unicode symbols + ANSI colors yang konsisten.
    """

    # ── Status Indicators ──────────────────────────────────
    OK = f"{_GREEN}{_BOLD}✦{_RESET}{_GREEN}"        # Success
    FAIL = f"{_RED}{_BOLD}✖{_RESET}{_RED}"           # Error/Failure
    WARN = f"{_YELLOW}{_BOLD}▲{_RESET}{_YELLOW}"     # Warning
    INFO = f"{_BLUE}{_BOLD}●{_RESET}{_BLUE}"         # Info
    WAIT = f"{_CYAN}◇{_RESET}{_CYAN}"               # Waiting/Pending

    # ── Data & Pipeline ────────────────────────────────────
    DATA = f"{_CYAN}{_BOLD}◆{_RESET}{_CYAN}"         # Data point
    CHART = f"{_MAGENTA}{_BOLD}▊{_RESET}{_MAGENTA}"  # Chart/Visual
    DB = f"{_BLUE}{_BOLD}⬡{_RESET}{_BLUE}"           # Database
    API = f"{_CYAN}{_BOLD}⬢{_RESET}{_CYAN}"          # API/Network
    CANDLE = f"{_YELLOW}{_BOLD}┃{_RESET}{_YELLOW}"   # Candlestick/OHLC

    # ── Lifecycle ──────────────────────────────────────────
    START = f"{_GREEN}{_BOLD}▶{_RESET}{_GREEN}"       # Start
    STOP = f"{_RED}{_BOLD}■{_RESET}{_RED}"            # Stop
    PLUG = f"{_DIM}◌{_RESET}"                         # Disconnect

    # ── Test Results ───────────────────────────────────────
    PASS = f"{_GREEN}{_BOLD}✦ PASS{_RESET}"
    FAILED = f"{_RED}{_BOLD}✖ FAIL{_RESET}"
    SKIP = f"{_YELLOW}{_BOLD}▷ SKIP{_RESET}"

    # ── Decorative ─────────────────────────────────────────
    BULLET = f"{_DIM}›{_RESET}"
    LINE = f"{_DIM}{'─' * 60}{_RESET}"
    DLINE = f"{_DIM}{'═' * 60}{_RESET}"
    CLEAN = f"{_DIM}○{_RESET}"                        # Cleanup

    # ── Colors for wrapping text ───────────────────────────
    GREEN = _GREEN
    RED = _RED
    YELLOW = _YELLOW
    BLUE = _BLUE
    CYAN = _CYAN
    MAGENTA = _MAGENTA
    WHITE = _WHITE
    BOLD = _BOLD
    DIM = _DIM
    R = _RESET  # Reset shorthand


def styled_header(title: str, width: int = 60) -> str:
    """Create a styled box header for test/section titles."""
    border = f"{_DIM}{'━' * width}{_RESET}"
    padded = title.center(width)
    return f"\n{border}\n{_BOLD}{_WHITE}  {padded}{_RESET}\n{border}"


def styled_summary(results: list[tuple[str, bool]]) -> tuple[bool, str]:
    """
    Generate a styled test summary from a list of (name, passed) tuples.
    Returns (all_passed, formatted_string).
    """
    lines = []
    lines.append(f"\n{S.DLINE}")
    lines.append(f"  {_BOLD}{_WHITE}SUMMARY{_RESET}")
    lines.append(S.DLINE)

    all_pass = True
    for name, passed in results:
        status = S.PASS if passed else S.FAILED
        lines.append(f"  {status}  {_WHITE}{name}{_RESET}")
        if not passed:
            all_pass = False

    lines.append(S.DLINE)
    if all_pass:
        lines.append(f"  {S.OK} {_GREEN}{_BOLD}All tests passed!{_RESET}")
    else:
        lines.append(f"  {S.WARN} {_YELLOW}Some tests failed!{_RESET}")

    return all_pass, "\n".join(lines)
