"""
Bank of Kigali - T24 Test Automation
Release-Readiness Dashboard
Built by Inlaks Computers Limited
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


# ============================================================
# PATHS  (defined before set_page_config - page_icon needs LOGO_PATH)
# ============================================================
REPORTS_DIR = "reports"
HISTORY_DIR = "reports/history"
SCREENSHOTS_DIR = "reports/screenshots"
LOGO_PATH = "dashboard/assets/bank_of_kigali_logo.png"
PERF_RESULTS_DIR = "performance/results"
PERF_LOCUSTFILE = "performance/locustfile.py"

st.set_page_config(
    page_title="Bank of Kigali - T24 Test Automation",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🏦",
    layout="wide",
)

# ============================================================
# CONSTANTS
# ============================================================
PRIMARY = "#003366"
ACCENT = "#D4AF37"
PASS_COLOR = "#10b981"
FAIL_COLOR = "#ef4444"
SKIP_COLOR = "#94a3b8"
INK = "#0f172a"
MUTED = "#64748b"

TIER_ORDER = ["smoke", "regression", "e2e", "negative"]

TIER_LABELS = {
    "smoke": "Smoke",
    "regression": "Regression",
    "e2e": "End-to-End",
    "negative": "Negative",
    "other": "Other",
}

TIER_DESCRIPTIONS = {
    "smoke": "Navigation, login, form loading",
    "regression": "INPUT flows, validations, commits",
    "e2e": "Cross-application, dual-control lifecycles",
    "negative": "Compliance & validation gap detection",
}

PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
DEFAULT_PAGE_SIZE = 25

AA_STEP_LABELS = {
    "01_aa_product_catalog": "AA product catalogue opened",
    "02_aa_term_deposit_products": "Term deposit products listed",
    "03_aa_input_form": "New arrangement input form loaded",
    "04_aa_header_filled": "Customer and currency captured",
    "05_aa_validated_settlement_fields": "Arrangement allocated and settlement fields shown",
    "06_aa_settlement_filled": "Settlement accounts captured",
    "07_aa_revalidated": "Arrangement revalidated",
    "08_aa_before_commit": "Ready to commit",
    "09_aa_commit_clicked": "Commit submitted",
    "10_aa_warning_answered": "Commit warning answered",
    "11_aa_override_prompt": "Override prompt displayed",
    "12_aa_override_accepted": "Override accepted",
    "13_aa_committed_final": "Input complete with T24 confirmation",
    "14_aa_inputter_signed_off": "Inputter signed off",
    "15_aa_authoriser_signed_in": "Authoriser signed in",
    "16_aa_auth_search_loaded": "Unauthorized AAA search loaded",
    "17_aa_auth_results_loaded": "Unauthorized AAA results found",
    "18_aa_auth_arrangement_selected": "Correct customer arrangement selected",
    "19_aa_auth_approval_drillbox": "Approval choice displayed",
    "20_aa_auth_approve_selected": "Approve drilldown selected",
    "21_aa_auth_toolbar_loaded": "Final authorise toolbar loaded",
    "22_aa_authorise_attempted": "AA arrangement authorised",
    "PASS_test_aa_term_deposit_input": "AA term deposit lifecycle passed",
    "FAIL_test_aa_term_deposit_input": "AA term deposit lifecycle failed",
}

# Minimal, intentional styling
st.markdown(f"""
<style>
    .main .block-container {{ padding-top: 1.8rem; max-width: 1400px; }}
    h1, h2 {{ color: {PRIMARY}; }}
    h3 {{ color: {INK}; }}
    [data-testid="stMetricValue"] {{ font-size: 1.9rem; color: {INK}; }}
    [data-testid="stMetricLabel"] {{ font-size: 0.85rem; color: {MUTED}; }}

    .brand-title {{ color: {PRIMARY}; font-size: 2.1rem; font-weight: 700;
                    margin: 0; line-height: 1.1; letter-spacing: -0.01em; }}
    .brand-sub   {{ color: #334155; font-size: 1.05rem; margin: 0.25rem 0 0;
                    font-weight: 400; }}
    .brand-tag   {{ color: {MUTED}; font-size: 0.8rem; margin: 0.5rem 0 0;
                    letter-spacing: 0.06em; text-transform: uppercase; }}

    .tier-badge {{
        display:inline-block; padding:.15rem .55rem; border-radius:6px;
        font-size:.7rem; font-weight:600; text-transform:uppercase;
        letter-spacing:.04em;
    }}
    .tier-smoke      {{ background:#e0f2fe; color:#075985; }}
    .tier-regression {{ background:#fef3c7; color:#854d0e; }}
    .tier-e2e        {{ background:#ede9fe; color:#5b21b6; }}
    .tier-other      {{ background:#f1f5f9; color:#475569; }}
    .tier-negative   {{ background:#fee2e2; color:#991b1b; }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# TEST RUNNER HELPERS
# ============================================================
def run_pytest_streaming(args_list, label, status_ph, log_ph):
    """Run pytest in a subprocess and stream output to placeholders."""
    cmd = [sys.executable, "-m", "pytest"] + args_list + [
        "-v", "--tb=short", "--color=no",
    ]
    cmd_display = " ".join(["pytest"] + args_list)
    status_ph.info(f"⏳  Running **{label}** - `{cmd_display}`")

    # Force UTF-8 - Windows subprocess defaults to cp1252 which crashes
    # on emoji/unicode in pytest output or conftest print statements.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    log_lines = []
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            encoding="utf-8",
            errors="replace",
        )

        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            log_lines.append(line.rstrip())
            log_ph.code("\n".join(log_lines[-40:]), language="text")

        process.wait()

        if process.returncode == 0:
            status_ph.success(f"✅  **{label}** complete - all tests passed")
        elif process.returncode == 1:
            status_ph.warning(
                f"⚠️  **{label}** complete - some tests failed. "
                "Check the **All Tests** tab for details."
            )
        elif process.returncode == 5:
            status_ph.warning(
                f"⚠️  **{label}** - no tests matched the selection. "
                "Verify the test files exist and markers are set."
            )
        else:
            status_ph.error(
                f"❌  **{label}** aborted (exit code {process.returncode})"
            )

        st.cache_data.clear()
        return process.returncode

    except Exception as e:
        status_ph.error(f"Error running tests: {e}")
        return -1


def default_perf_target():
    raw = os.getenv("BW_URL", "")
    if not raw:
        return "http://localhost", "/"
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/"), "/"
    host = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return host, path


def locust_command_base():
    venv_locust = Path("tester/Scripts/locust.exe")
    if venv_locust.exists():
        return [str(venv_locust)]
    return [sys.executable, "-m", "locust"]


def run_locust_headless(config, status_ph, log_ph):
    """Run Locust headless and return the results directory path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result_dir = Path(PERF_RESULTS_DIR) / f"run-{timestamp}"
    result_dir.mkdir(parents=True, exist_ok=True)
    csv_prefix = result_dir / "stats"
    html_report = result_dir / "report.html"
    stdout_log = result_dir / "stdout.log"

    cmd = locust_command_base() + [
        "-f", PERF_LOCUSTFILE,
        "--headless",
        "-u", str(config["users"]),
        "-r", str(config["spawn_rate"]),
        "-t", config["duration"],
        "--host", config["host"],
        "--csv", str(csv_prefix),
        "--html", str(html_report),
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PERF_PATHS"] = "\n".join(config["paths"])
    env["PERF_MIN_WAIT"] = str(config["min_wait"])
    env["PERF_MAX_WAIT"] = str(config["max_wait"])
    env["PERF_LOGIN_ENABLED"] = "1" if config["login_enabled"] else "0"
    env["PERF_LOGIN_USER"] = config.get("login_user", "")
    env["PERF_LOGIN_PASS"] = config.get("login_pass", "")
    env["PERF_LOGIN_PATH"] = config.get(
        "login_path", "/BrowserWeb/servlet/BrowserLoginServlet")

    status_ph.info(
        f"Running performance test: {config['users']} users, "
        f"{config['spawn_rate']}/s spawn, duration {config['duration']}"
    )

    lines = []
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        with open(stdout_log, "w", encoding="utf-8") as f:
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break
                line = line.rstrip()
                lines.append(line)
                f.write(line + "\n")
                log_ph.code("\n".join(lines[-40:]), language="text")
        process.wait()
        if process.returncode == 0:
            status_ph.success(f"Performance run complete: {result_dir}")
        else:
            status_ph.error(
                f"Performance run ended with exit code {process.returncode}. "
                f"See {stdout_log}."
            )
        return str(result_dir)
    except Exception as e:
        status_ph.error(f"Could not run Locust: {e}")
        return str(result_dir)


def latest_perf_runs():
    root = Path(PERF_RESULTS_DIR)
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def load_perf_stats(result_dir):
    stats_path = Path(result_dir) / "stats_stats.csv"
    if not stats_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(stats_path)
    except Exception:
        return pd.DataFrame()


def load_perf_failures(result_dir):
    failures_path = Path(result_dir) / "stats_failures.csv"
    if not failures_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(failures_path)
    except Exception:
        return pd.DataFrame()


def perf_total_row(stats_df):
    if stats_df.empty:
        return {}

    name_col = "Name" if "Name" in stats_df.columns else None
    type_col = "Type" if "Type" in stats_df.columns else None
    candidates = pd.DataFrame()
    if name_col:
        candidates = stats_df[
            stats_df[name_col].astype(str).str.lower().isin(
                ["aggregated", "total"]
            )
        ]
    if candidates.empty and type_col:
        candidates = stats_df[
            stats_df[type_col].astype(str).str.lower().isin(
                ["aggregated", "total"]
            )
        ]
    if candidates.empty:
        candidates = stats_df.tail(1)
    return candidates.iloc[-1].to_dict()


def perf_value(row, *names, default=0):
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return default


def format_perf_number(value, decimals=1):
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "0"


def discover_test_files():
    """Scan tests/ for test files. Returns sorted list of relative paths."""
    found = []
    for root_dir in ["tests/smoke", "tests/regression"]:
        if os.path.exists(root_dir):
            for f in sorted(os.listdir(root_dir)):
                if f.startswith("test_") and f.endswith(".py"):
                    found.append(f"{root_dir}/{f}")
    return found


# ============================================================
# DATA LAYER
# ============================================================
def detect_tier(test_id: str) -> str:
    test_func = test_id.split("::")[-1].lower()

    if (
        test_func.startswith("test_compliance_")
        or test_func.startswith("test_negative_")
        or "negative_scenarios" in test_id.lower()
    ):
        return "negative"

    if "/smoke/" in test_id:
        return "smoke"
    if "e2e" in test_id.lower():
        return "e2e"
    if "/regression/" in test_id:
        return "regression"
    return "other"


def journey_name(test_id: str) -> str:
    base = test_id.split("::")[-1].replace("test_", "")
    return base.replace("_", " ").title()


def format_duration(seconds: float) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"


def format_datetime(dt: datetime, with_seconds: bool = False) -> str:
    fmt = "%d %b %Y, %H:%M:%S" if with_seconds else "%d %b %Y, %H:%M"
    return dt.strftime(fmt)


@st.cache_data(ttl=5)
def load_runs() -> list:
    """Load every run report (current + archived) sorted newest-first."""
    runs = []
    current = os.path.join(REPORTS_DIR, "report.json")
    if os.path.exists(current):
        try:
            with open(current) as f:
                d = json.load(f)
                d["__source"] = "current"
                d["__filepath"] = current
                runs.append(d)
        except Exception:
            pass

    if os.path.exists(HISTORY_DIR):
        for p in sorted(glob.glob(os.path.join(HISTORY_DIR, "run-*.json"))):
            try:
                with open(p) as f:
                    d = json.load(f)
                    d["__source"] = "archive"
                    d["__filepath"] = p
                    runs.append(d)
            except Exception:
                continue

    runs.sort(key=lambda r: r.get("created", 0), reverse=True)
    return runs


def extract_tests(run: dict) -> pd.DataFrame:
    columns = [
        "test_id", "tier", "journey", "outcome",
        "setup", "call", "teardown", "duration",
        "message", "run_timestamp", "run_source",
    ]

    rows = []
    run_created = run.get("created", 0)
    run_dt = datetime.fromtimestamp(run_created)
    for t in run.get("tests", []):
        nodeid = t.get("nodeid", "")
        setup_d = t.get("setup", {}).get("duration", 0)
        call_d = t.get("call", {}).get("duration", 0)
        teardown_d = t.get("teardown", {}).get("duration", 0)
        rows.append({
            "test_id": nodeid,
            "tier": detect_tier(nodeid),
            "journey": journey_name(nodeid),
            "outcome": t.get("outcome", "unknown"),
            "setup": setup_d,
            "call": call_d,
            "teardown": teardown_d,
            "duration": setup_d + call_d + teardown_d,
            "message": (
                t.get("call", {}).get("longrepr", "")
                if t.get("outcome") == "failed" else ""
            ),
            "run_timestamp": run_dt,
            "run_source": run.get("__source", "?"),
        })

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def extract_all_tests(runs: list) -> pd.DataFrame:
    """Every test instance from every run, with a stable UID for selection."""
    frames = [extract_tests(r) for r in runs]
    if not frames:
        return pd.DataFrame(
            columns=list(extract_tests({}).columns) + ["uid"]
        )

    df = pd.concat(frames, ignore_index=True)

    if df.empty:
        # All runs were empty - return same schema with uid column added
        df["uid"] = pd.Series(dtype=str)
        return df

    df["uid"] = df.apply(
        lambda r: f"{r['run_timestamp'].isoformat()}|{r['test_id']}",
        axis=1,
    )
    return df


def run_summary(run: dict) -> dict:
    s = run.get("summary", {})
    total = s.get("total", 0)
    return {
        "timestamp": datetime.fromtimestamp(run.get("created", 0)),
        "total": total,
        "passed": s.get("passed", 0),
        "failed": s.get("failed", 0),
        "skipped": s.get("skipped", 0),
        "pass_rate": (s.get("passed", 0) / total * 100) if total else 0,
        "duration": run.get("duration", 0),
        "source": run.get("__source", "?"),
    }


def tests_summary(tests_df: pd.DataFrame, timestamp=None,
                  source: str = "selected") -> dict:
    total = len(tests_df)
    passed = int((tests_df["outcome"] == "passed").sum()) if total else 0
    failed = int((tests_df["outcome"] == "failed").sum()) if total else 0
    skipped = int((tests_df["outcome"] == "skipped").sum()) if total else 0
    duration = float(tests_df["duration"].sum()) if total else 0
    if timestamp is None:
        if total and "run_timestamp" in tests_df:
            timestamp = tests_df["run_timestamp"].max()
        else:
            timestamp = datetime.now()
    return {
        "timestamp": timestamp,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": (passed / total * 100) if total else 0,
        "duration": duration,
        "source": source,
    }


def all_screenshots() -> list:
    if not os.path.exists(SCREENSHOTS_DIR):
        return []
    return sorted(glob.glob(os.path.join(SCREENSHOTS_DIR, "*.png")))


def screenshot_caption(path: str) -> str:
    stem = Path(path).stem
    return AA_STEP_LABELS.get(stem, stem.replace("_", " ").title())


def journey_screenshot_filter(test_id: str, path: str) -> bool:
    stem = Path(path).stem
    test_func = test_id.split("::")[-1].lower()

    if "aa_term_deposit" in test_func:
        return stem in AA_STEP_LABELS or "_aa_" in stem
    if "funds_transfer" in test_func:
        return "_ft_" in stem or "funds_transfer" in stem
    if "account" in test_func:
        return "_account_" in stem or "account_" in stem
    if "customer" in test_func:
        return "_customer_" in stem or "customer_" in stem
    if "login" in test_func:
        return "login" in stem.lower()
    if "logout" in test_func or "sign_off" in test_func:
        return "logout" in stem.lower() or "signed_off" in stem.lower()
    return False


def load_state_json(filename: str) -> dict:
    path = Path(REPORTS_DIR) / "state" / filename
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def screenshots_for_test(test_id: str, outcome: str,
                         is_latest_run: bool) -> dict:
    """Locate screenshots associated with a test.

    'auto'    - PASS_/FAIL_ shots whose filename includes the test name.
                Match across all runs.
    'journey' - Numbered step shots (01_, 02_, ...). Only meaningful for
                the latest run (files are overwritten each run).
    'debug'   - DEBUG_ shots. Only retained for the latest run.
    """
    test_func = test_id.split("::")[-1]
    shots = all_screenshots()

    auto = [
        s for s in shots
        if (Path(s).stem.startswith(("FAIL_", "PASS_"))
            and test_func in Path(s).stem)
    ]

    journey, debug = [], []
    if is_latest_run:
        for s in shots:
            stem = Path(s).stem
            if re.match(r"^\d+_", stem) and journey_screenshot_filter(test_id, s):
                journey.append(s)
            elif stem.startswith("DEBUG_") and journey_screenshot_filter(test_id, s):
                debug.append(s)

    return {
        "auto": sorted(auto),
        "journey": sorted(journey),
        "debug": sorted(debug),
    }


def parse_t24_error(longrepr: str) -> dict:
    result = {"headline": None, "why": None, "fix": None}
    if not longrepr:
        return result
    h = re.search(r"T24TestError:\s*(.+?)(?=\n|$)", longrepr)
    if h:
        result["headline"] = h.group(1).strip()
    w = re.search(
        r"Why:\s*(.+?)(?=\nE\s+(?:Fix|How to fix|$)|$)",
        longrepr, re.DOTALL,
    )
    if w:
        result["why"] = re.sub(r"\s+", " ", w.group(1)).strip()
    f = re.search(r"(?:Fix|How to fix):\s*(.+?)$", longrepr, re.DOTALL)
    if f:
        result["fix"] = re.sub(r"\s+", " ", f.group(1)).strip()
    return result


# ============================================================
# PDF REPORT GENERATION
# ============================================================
def _pdf_escape(text) -> str:
    """Escape XML-special chars so reportlab's Paragraph parser does not
    choke on error text containing < > or &."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def generate_pdf_report(
        runs, latest_summary, latest_tests,
        report_title="T24 Test Automation - Release-Readiness Report",
        scope_label="Latest Run",
):
    """Build a release-readiness PDF with the BoK logo, summary,
    test results table, and failure forensics. Returns bytes."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, inch
    from reportlab.platypus import (
        Image, PageBreak, Paragraph, SimpleDocTemplate,
        Spacer, Table, TableStyle,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="Bank of Kigali - T24 Test Automation Report",
        author="Inlaks Computers Limited",
    )

    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        "BrandTitle", parent=styles["Heading1"],
        fontSize=22, textColor=colors.HexColor(PRIMARY),
        spaceAfter=4, alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "BrandSub", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#334155"),
        spaceAfter=20,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor(PRIMARY),
        spaceBefore=14, spaceAfter=10,
    )
    fail_head_style = ParagraphStyle(
        "FailHead", parent=styles["Heading3"],
        fontSize=12, textColor=colors.HexColor(INK),
        spaceBefore=10, spaceAfter=4,
    )
    cell_style = ParagraphStyle(
        "Cell", parent=styles["Normal"],
        fontSize=9, leading=11,
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor(MUTED),
        alignment=TA_CENTER,
    )

    # ----- Logo + brand header -----
    if os.path.exists(LOGO_PATH):
        try:
            elements.append(Image(LOGO_PATH, width=2.2 * inch,
                                  height=1.1 * inch, kind="proportional"))
            elements.append(Spacer(1, 10))
        except Exception:
            pass

    elements.append(Paragraph("Bank of Kigali", title_style))
    elements.append(Paragraph(report_title, subtitle_style))

    # ----- Metadata -----
    meta = [
        ["Report Generated", datetime.now().strftime("%d %B %Y, %H:%M")],
        [scope_label, latest_summary["timestamp"].strftime("%d %B %Y, %H:%M")],
        ["Total Runs on Record", str(len(runs))],
        ["Evidence Duration", format_duration(latest_summary["duration"])],
    ]
    meta_tbl = Table(meta, colWidths=[5 * cm, 10 * cm])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor(MUTED)),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor(INK)),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_tbl)

    # ----- KPI summary -----
    elements.append(Paragraph(f"{scope_label} Summary", section_style))
    kpis = [
        ["Total", "Passed", "Failed", "Skipped", "Pass Rate"],
        [
            str(latest_summary["total"]),
            str(latest_summary["passed"]),
            str(latest_summary["failed"]),
            str(latest_summary["skipped"]),
            f"{latest_summary['pass_rate']:.1f}%",
        ],
    ]
    kpi_tbl = Table(kpis, colWidths=[3 * cm] * 5)
    kpi_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 13),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(kpi_tbl)

    # ----- Tier breakdown -----
    elements.append(Paragraph("Tier Breakdown", section_style))
    tier_rows = [["Tier", "Total", "Passed", "Failed", "Pass Rate"]]
    for tier in TIER_ORDER:
        tdf = latest_tests[latest_tests["tier"] == tier]
        t_total = len(tdf)
        t_passed = int((tdf["outcome"] == "passed").sum())
        t_failed = int((tdf["outcome"] == "failed").sum())
        t_rate = (t_passed / t_total * 100) if t_total else 0
        tier_rows.append([
            TIER_LABELS[tier],
            str(t_total),
            str(t_passed),
            str(t_failed),
            f"{t_rate:.0f}%" if t_total else "-",
        ])
    tier_tbl = Table(tier_rows, colWidths=[3.5 * cm, 2.5 * cm, 2.5 * cm,
                                           2.5 * cm, 3 * cm])
    tier_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    elements.append(tier_tbl)

    # ----- Per-test results -----
    elements.append(PageBreak())
    elements.append(Paragraph("Test Results", section_style))

    test_rows = [["Tier", "Journey", "Status", "Duration"]]
    for _, row in latest_tests.iterrows():
        status_text = {
            "passed":  "Passed",
            "failed":  "Failed",
            "skipped": "Skipped",
        }.get(row["outcome"], row["outcome"])
        test_rows.append([
            TIER_LABELS.get(row["tier"], row["tier"]),
            Paragraph(_pdf_escape(row["journey"]), cell_style),
            status_text,
            format_duration(row["duration"]),
        ])

    results_tbl = Table(
        test_rows,
        colWidths=[2.5 * cm, 7.5 * cm, 2.5 * cm, 2.5 * cm],
        repeatRows=1,
    )

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if len(test_rows) > 1:
        style_cmds.append(
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f8fafc")])
        )
    # Colour the status cells
    for i, row in enumerate(test_rows[1:], start=1):
        status = row[2]
        if status == "Passed":
            style_cmds.append(("TEXTCOLOR", (2, i), (2, i),
                               colors.HexColor("#047857")))
        elif status == "Failed":
            style_cmds.append(("TEXTCOLOR", (2, i), (2, i),
                               colors.HexColor("#b91c1c")))
        else:
            style_cmds.append(("TEXTCOLOR", (2, i), (2, i),
                               colors.HexColor(MUTED)))
    results_tbl.setStyle(TableStyle(style_cmds))
    elements.append(results_tbl)

    # ----- Failure forensics -----
    failed = latest_tests[latest_tests["outcome"] == "failed"]
    if not failed.empty:
        elements.append(PageBreak())
        elements.append(Paragraph("Failure Analysis", section_style))

        for _, t in failed.iterrows():
            parsed = parse_t24_error(t["message"])
            elements.append(Paragraph(
                f"<b>{_pdf_escape(t['journey'])}</b>  "
                f"<font color='{MUTED}' size='9'>"
                f"({_pdf_escape(TIER_LABELS.get(t['tier'], t['tier']))})"
                f"</font>",
                fail_head_style,
            ))
            if parsed["headline"]:
                elements.append(Paragraph(
                    f"<b>What happened:</b> {_pdf_escape(parsed['headline'])}",
                    styles["Normal"],
                ))
            if parsed["why"]:
                elements.append(Paragraph(
                    f"<b>Why:</b> {_pdf_escape(parsed['why'])}",
                    styles["Normal"],
                ))
            if parsed["fix"]:
                elements.append(Paragraph(
                    f"<b>How to fix:</b> {_pdf_escape(parsed['fix'])}",
                    styles["Normal"],
                ))
            if not any([parsed["headline"], parsed["why"], parsed["fix"]]):
                elements.append(Paragraph(
                    "See the dashboard for the full technical traceback.",
                    styles["Normal"],
                ))
            elements.append(Spacer(1, 8))

    # ----- Footer -----
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        "Generated by Inlaks Computers Limited \u2014 "
        "T24 Test Automation Framework",
        footer_style,
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ============================================================
# STATE
# ============================================================
def init_state():
    defaults = {
        "selected_uid": None,
        "test_page": 0,
        "page_size": DEFAULT_PAGE_SIZE,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# ============================================================
# HEADER
# ============================================================
col_logo, col_title, col_meta = st.columns([1, 6, 2], gap="large")

with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown(
            f"""<div style='background:{PRIMARY};color:white;padding:2.5rem 1rem;
                border-radius:10px;text-align:center;font-weight:700;
                font-size:2rem;letter-spacing:.05em;'>BoK</div>""",
            unsafe_allow_html=True,
        )

with col_title:
    st.markdown(
        """<p class='brand-title'>Bank of Kigali</p>
           <p class='brand-sub'>T24 Test Automation &middot; Release-Readiness Dashboard</p>
           <p class='brand-tag'>Built by Inlaks Computers Limited</p>""",
        unsafe_allow_html=True,
    )

with col_meta:
    st.markdown("")  # vertical spacer
    if st.button("🔄  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Updated {datetime.now().strftime('%H:%M:%S')}")

st.divider()

# ============================================================
# LOAD
# ============================================================
runs = load_runs()
if not runs:
    st.warning("No test runs found yet. Run `pytest` to generate the first report.")
    st.stop()

latest = runs[0]
latest_summary = run_summary(latest)
latest_tests = extract_tests(latest)
all_tests = extract_all_tests(runs)
if not all_tests.empty:
    all_tests["run_timestamp"] = pd.to_datetime(all_tests["run_timestamp"])
hist_summaries = pd.DataFrame([run_summary(r) for r in runs]).iloc[::-1]
if not hist_summaries.empty:
    hist_summaries["timestamp"] = pd.to_datetime(hist_summaries["timestamp"])

if latest_summary["total"] == 0:
    st.warning(
        "⚠️  The most recent pytest run produced **0 tests collected**. "
        "This usually means pytest crashed during startup (often a "
        "Unicode error in `conftest.py` when run as a Windows subprocess) "
        "or no tests matched the selection. Trigger a fresh run from "
        "the **Test Runner** tab to refresh."
    )

# ----- Pre-generate the PDF once per render (reused by all download buttons).
#       Wrapped so a missing reportlab degrades gracefully. -----
pdf_report_bytes = None
pdf_error = None
try:
    pdf_report_bytes = generate_pdf_report(runs, latest_summary, latest_tests)
except ImportError:
    pdf_error = "reportlab is not installed - run `pip install reportlab`."
except Exception as e:
    pdf_error = f"PDF report could not be generated ({e})."


def render_pdf_download(key: str, label: str, caption: str = ""):
    """Render a PDF download button, or a fallback caption on failure."""
    if pdf_report_bytes:
        st.download_button(
            label=label,
            data=pdf_report_bytes,
            file_name=(
                f"BoK_T24_Report_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            ),
            mime="application/pdf",
            use_container_width=True,
            key=key,
        )
        if caption:
            st.caption(caption)
    else:
        st.caption(f"📄  {pdf_error}")


def render_pdf_bytes_download(pdf_bytes, key: str, label: str,
                              filename_prefix: str, caption: str = ""):
    """Render a download button for a scoped PDF report."""
    if not pdf_bytes:
        st.caption("Report could not be generated.")
        return
    st.download_button(
        label=label,
        data=pdf_bytes,
        file_name=(
            f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        ),
        mime="application/pdf",
        use_container_width=True,
        key=key,
    )
    if caption:
        st.caption(caption)


# ============================================================
# KPI STRIP
# ============================================================
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(
    "Latest Pass Rate",
    f"{latest_summary['pass_rate']:.0f}%",
    f"{latest_summary['passed']}/{latest_summary['total']} tests",
)
k2.metric("Tests Run (Latest)", latest_summary["total"])
k3.metric(
    "Failures (Latest)",
    latest_summary["failed"],
    delta=None if latest_summary["failed"] == 0 else f"{latest_summary['failed']} failed",
    delta_color="inverse",
)
k4.metric("Total Runs on Record", len(runs))
k5.metric(
    "Last Run",
    latest_summary["timestamp"].strftime("%d %b"),
    latest_summary["timestamp"].strftime("%H:%M"),
)

st.divider()

# ============================================================
# TABS
# ============================================================
tab_overview, tab_tests, tab_history, tab_runner = st.tabs([
    "📊  Overview",
    "🔍  All Tests",
    "📈  Run History",
    "▶️  Test Runner",
])

# -------------------- OVERVIEW --------------------
with tab_overview:
    st.subheader("Latest Run Report")
    lr1, lr2, lr3, lr4 = st.columns(4)
    lr1.metric("Run Time", format_datetime(latest_summary["timestamp"]))
    lr2.metric("Status", "Ready" if latest_summary["failed"] == 0 else "Review")
    lr3.metric("Pass Rate", f"{latest_summary['pass_rate']:.1f}%")
    lr4.metric("Duration", format_duration(latest_summary["duration"]))
    st.caption(
        "Latest run evidence is shown here. Individual journey evidence and "
        "screenshots are available under All Tests."
    )
    st.divider()

    st.subheader("Test Outcomes - All Runs")

    c1, c2 = st.columns(2, gap="large")

    with c1:
        oc = all_tests["outcome"].value_counts().to_dict() if not all_tests.empty else {}
        if oc:
            labels = [k.title() for k in oc]
            colors = [
                PASS_COLOR if k == "passed"
                else FAIL_COLOR if k == "failed"
                else SKIP_COLOR
                for k in oc
            ]
            fig = go.Figure(go.Pie(
                labels=labels,
                values=list(oc.values()),
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="white", width=2)),
                textfont=dict(size=14, color="white"),
                textposition="inside",
                textinfo="label+percent",
            ))
            fig.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text="Aggregate Outcome Distribution",
                           font=dict(size=14, color=INK)),
                showlegend=True,
                legend=dict(orientation="h", y=-0.05),
            )
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if len(hist_summaries) >= 2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hist_summaries["timestamp"],
                y=hist_summaries["pass_rate"],
                mode="lines+markers",
                line=dict(color=PRIMARY, width=3),
                marker=dict(size=10, color=PRIMARY),
                fill="tozeroy",
                fillcolor="rgba(0,51,102,0.08)",
            ))
            fig.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text="Pass Rate Trend",
                           font=dict(size=14, color=INK)),
                yaxis=dict(range=[0, 105], title="Pass Rate (%)"),
                xaxis_title="",
                plot_bgcolor="white",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run pytest 2+ times to populate the trend chart.")

    st.subheader("Test Pyramid - Latest Run")

    tcols = st.columns(len(TIER_ORDER), gap="medium")
    for col, tier in zip(tcols, TIER_ORDER):
        tdf = latest_tests[latest_tests["tier"] == tier]
        total = len(tdf)
        passed = int((tdf["outcome"] == "passed").sum())
        failed = int((tdf["outcome"] == "failed").sum())
        rate = (passed / total * 100) if total else 0
        bar_color = (
            PASS_COLOR if (failed == 0 and total > 0)
            else FAIL_COLOR if failed > 0
            else SKIP_COLOR
        )
        with col:
            st.metric(TIER_LABELS[tier], f"{rate:.0f}%" if total else "-",
                      f"{passed}/{total} passed")
            st.markdown(
                f"""<div style='background:#f1f5f9;height:8px;border-radius:4px;
                    overflow:hidden;margin:0.5rem 0;'>
                    <div style='background:{bar_color};height:100%;
                        width:{rate}%;transition:width .3s;'></div>
                </div>""",
                unsafe_allow_html=True,
            )
            st.caption(TIER_DESCRIPTIONS[tier])

    # ----- Release-readiness PDF -----
    st.divider()
    st.subheader("Readiness Report Scope")
    if not all_tests.empty:
        min_date = all_tests["run_timestamp"].min().date()
        max_date = all_tests["run_timestamp"].max().date()
        rc1, rc2, rc3 = st.columns([2, 2, 3])
        with rc1:
            report_dates = st.date_input(
                "Run date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="overview_report_dates",
            )
        with rc2:
            report_status = st.multiselect(
                "Statuses",
                options=["passed", "failed", "skipped"],
                default=["passed", "failed", "skipped"],
                format_func=lambda x: x.title(),
                key="overview_report_status",
            )
        with rc3:
            report_tiers = st.multiselect(
                "Tiers",
                options=TIER_ORDER,
                default=TIER_ORDER,
                format_func=lambda x: TIER_LABELS[x],
                key="overview_report_tiers",
            )
        if isinstance(report_dates, tuple):
            start_date, end_date = report_dates
        else:
            start_date = end_date = report_dates
        scoped_tests = all_tests[
            (all_tests["run_timestamp"].dt.date >= start_date)
            & (all_tests["run_timestamp"].dt.date <= end_date)
            & all_tests["outcome"].isin(report_status)
            & all_tests["tier"].isin(report_tiers)
        ].copy()
        scoped_summary = tests_summary(
            scoped_tests,
            timestamp=latest_summary["timestamp"],
            source="filtered",
        )
        st.caption(
            f"Selected report scope includes {len(scoped_tests)} test result(s) "
            f"from {start_date} to {end_date}."
        )
    else:
        scoped_tests = latest_tests
        scoped_summary = latest_summary

    try:
        scoped_pdf = generate_pdf_report(
            runs,
            scoped_summary,
            scoped_tests,
            report_title="T24 Test Automation - Readiness Report",
            scope_label="Selected Scope",
        )
    except Exception:
        scoped_pdf = None

    dl1, dl2 = st.columns([1, 3])
    with dl1:
        render_pdf_bytes_download(
            scoped_pdf,
            key="pdf_dl_overview",
            label="📄  Download Readiness Report (PDF)",
            filename_prefix="BoK_T24_Readiness_Report",
        )
    with dl2:
        st.caption(
            "Comprehensive report for the selected date, status, and tier "
            "scope. Use All Tests for a single-test evidence report."
        )

# -------------------- ALL TESTS --------------------
with tab_tests:
    st.subheader("Test Log")
    st.caption(
        "Every test instance across every run, newest first. "
        "Click a row to see its full report."
    )

    # ----- Filters -----
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
    with fc1:
        tier_filter = st.multiselect(
            "Tier",
            options=TIER_ORDER,
            default=TIER_ORDER,
            format_func=lambda x: TIER_LABELS[x],
        )
    with fc2:
        status_filter = st.multiselect(
            "Status",
            options=["passed", "failed", "skipped"],
            default=["passed", "failed", "skipped"],
            format_func=lambda x: x.title(),
        )
    with fc3:
        page_size = st.selectbox(
            "Rows per page",
            options=PAGE_SIZE_OPTIONS,
            index=PAGE_SIZE_OPTIONS.index(st.session_state.page_size),
        )
        if page_size != st.session_state.page_size:
            st.session_state.page_size = page_size
            st.session_state.test_page = 0
    with fc4:
        search = st.text_input(
            "Search journey",
            placeholder="e.g. customer, account, login",
        )

    # ----- Apply filters -----
    filtered = all_tests[
        all_tests["tier"].isin(tier_filter)
        & all_tests["outcome"].isin(status_filter)
        ]
    if search:
        filtered = filtered[
            filtered["journey"].str.contains(search, case=False, na=False)
        ]
    filtered = filtered.sort_values(
        "run_timestamp", ascending=False
    ).reset_index(drop=True)

    total_rows = len(filtered)

    # ----- Pagination -----
    if total_rows == 0:
        st.info("No tests match the current filters.")
    else:
        total_pages = max(1, (total_rows - 1) // page_size + 1)
        if st.session_state.test_page >= total_pages:
            st.session_state.test_page = 0

        start_idx = st.session_state.test_page * page_size
        end_idx = min(start_idx + page_size, total_rows)
        page_df = filtered.iloc[start_idx:end_idx].copy()

        # ----- Display table -----
        display = page_df.copy()
        display["Date/Time"] = display["run_timestamp"].apply(format_datetime)
        display["Tier"] = display["tier"].map(TIER_LABELS)
        display["Status"] = display["outcome"].map({
            "passed": "✅ Passed",
            "failed": "❌ Failed",
            "skipped": "⏭️  Skipped",
        })
        display["Duration"] = display["duration"].apply(format_duration)
        display["Journey"] = display["journey"]

        try:
            event = st.dataframe(
                display[["Date/Time", "Tier", "Journey", "Status", "Duration"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"test_table_{st.session_state.test_page}",
            )
            if event and event.selection and event.selection.rows:
                selected_local_idx = event.selection.rows[0]
                st.session_state.selected_uid = (
                    page_df.iloc[selected_local_idx]["uid"]
                )
        except TypeError:
            # Older Streamlit fallback - render table read-only, select via dropdown
            st.dataframe(
                display[["Date/Time", "Tier", "Journey", "Status", "Duration"]],
                use_container_width=True, hide_index=True,
            )
            options = list(range(len(page_df)))
            sel = st.selectbox(
                "Pick a test for detail",
                options=options,
                format_func=lambda i: (
                    f"{display.iloc[i]['Date/Time']} - "
                    f"{display.iloc[i]['Journey']} - "
                    f"{display.iloc[i]['Status']}"
                ),
            )
            if sel is not None:
                st.session_state.selected_uid = page_df.iloc[sel]["uid"]

        # ----- Pagination controls -----
        pc1, pc2, pc3, pc4, pc5 = st.columns([2, 1, 2, 1, 2])
        with pc1:
            st.caption(
                f"Showing **{start_idx + 1}-{end_idx}** of **{total_rows}** tests"
            )
        with pc2:
            if st.button("← Previous",
                         disabled=st.session_state.test_page == 0,
                         use_container_width=True):
                st.session_state.test_page -= 1
                st.rerun()
        with pc3:
            st.markdown(
                f"<div style='text-align:center;padding-top:.4rem;'>"
                f"Page <b>{st.session_state.test_page + 1}</b> of "
                f"<b>{total_pages}</b></div>",
                unsafe_allow_html=True,
            )
        with pc4:
            if st.button("Next →",
                         disabled=st.session_state.test_page >= total_pages - 1,
                         use_container_width=True):
                st.session_state.test_page += 1
                st.rerun()
        with pc5:
            pass

        # ----- Test detail panel -----
        if st.session_state.selected_uid:
            test_match = all_tests[all_tests["uid"] == st.session_state.selected_uid]
            if not test_match.empty:
                st.divider()

                # Header with back button
                hcol1, hcol2 = st.columns([8, 1])
                with hcol1:
                    st.markdown("### Test Detail")
                with hcol2:
                    if st.button("✕ Close", use_container_width=True):
                        st.session_state.selected_uid = None
                        st.rerun()

                test = test_match.iloc[0]
                is_from_latest = (
                        test["run_timestamp"] == hist_summaries["timestamp"].max()
                )

                outcome_emoji = {
                    "passed": "✅", "failed": "❌", "skipped": "⏭️"
                }.get(test["outcome"], "❔")

                # Headline
                tier_class = f"tier-{test['tier']}"
                st.markdown(
                    f"#### {outcome_emoji} {test['journey']}  "
                    f"<span class='tier-badge {tier_class}'>"
                    f"{TIER_LABELS[test['tier']]}</span>",
                    unsafe_allow_html=True,
                )

                # Metadata
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Status", test["outcome"].title())
                mc2.metric("Duration", format_duration(test["duration"]))
                mc3.metric("When", format_datetime(test["run_timestamp"]))
                mc4.metric("Run Source", test["run_source"].title())

                st.caption(f"**Test ID:** `{test['test_id']}`")

                # PDF download for the selected test only
                selected_test_df = pd.DataFrame([test.to_dict()])
                selected_summary = tests_summary(
                    selected_test_df,
                    timestamp=test["run_timestamp"],
                    source=test["run_source"],
                )
                try:
                    selected_pdf = generate_pdf_report(
                        runs,
                        selected_summary,
                        selected_test_df,
                        report_title=f"Test Evidence Report - {test['journey']}",
                        scope_label="Selected Test",
                    )
                except Exception:
                    selected_pdf = None
                pdc1, pdc2 = st.columns([1, 2])
                with pdc1:
                    render_pdf_bytes_download(
                        selected_pdf,
                        key="pdf_dl_detail",
                        label="📄  Download Selected-Test Report (PDF)",
                        filename_prefix="BoK_T24_Selected_Test_Report",
                    )
                with pdc2:
                    st.caption(
                        "Focused report for this selected test: status, timing, "
                        "and failure detail where applicable."
                    )

                # Failure forensics
                if test["outcome"] == "failed":
                    parsed = parse_t24_error(test["message"])
                    st.markdown("##### 🚨 Failure Analysis")
                    if parsed["headline"]:
                        st.error(f"**What happened:** {parsed['headline']}")
                    if parsed["why"]:
                        st.markdown(f"**Why:** {parsed['why']}")
                    if parsed["fix"]:
                        st.markdown(f"**How to fix:** {parsed['fix']}")
                    with st.expander("📋 Full technical traceback"):
                        st.code(
                            test["message"][:5000] or "(no traceback captured)",
                        )

                # Phase breakdown
                st.markdown("##### ⏱️ Phase Breakdown")
                phases_df = pd.DataFrame([
                    {"Phase": "Setup", "Duration": format_duration(test["setup"]),
                     "Seconds": round(test["setup"], 3)},
                    {"Phase": "Call (test body)",
                     "Duration": format_duration(test["call"]),
                     "Seconds": round(test["call"], 3)},
                    {"Phase": "Teardown",
                     "Duration": format_duration(test["teardown"]),
                     "Seconds": round(test["teardown"], 3)},
                    {"Phase": "Total",
                     "Duration": format_duration(test["duration"]),
                     "Seconds": round(test["duration"], 3)},
                ])
                st.dataframe(phases_df, use_container_width=True, hide_index=True)

                # Screenshots
                shots = screenshots_for_test(
                    test["test_id"], test["outcome"],
                    is_latest_run=is_from_latest,
                )

                if shots["auto"]:
                    st.markdown("##### 📸 Outcome Screenshot")
                    for s in shots["auto"]:
                        st.image(s, caption=screenshot_caption(s),
                                 use_container_width=True)

                if shots["journey"] and is_from_latest:
                    st.markdown(
                        f"##### 🗺️  Journey Evidence "
                        f"({len(shots['journey'])} screenshots)"
                    )
                    st.caption(
                        "Step-by-step visual evidence captured during the test."
                    )
                    for s in shots["journey"]:
                        st.image(s, caption=screenshot_caption(s),
                                 use_container_width=True)

                if shots["debug"] and is_from_latest:
                    st.markdown("##### 🔍 Debug Captures")
                    for s in shots["debug"]:
                        st.image(s, caption=screenshot_caption(s),
                                 use_container_width=True)

                if not any(shots.values()):
                    if is_from_latest:
                        st.info("No screenshots captured for this test.")
                    else:
                        st.info(
                            "Journey screenshot files are overwritten on each "
                            "run, so step-by-step evidence is only available "
                            "for the most recent run. The outcome screenshot "
                            "(PASS_/FAIL_) is retained if it was timestamped."
                        )

# -------------------- HISTORY --------------------
with tab_history:
    if len(runs) < 2:
        st.info(
            f"Only {len(runs)} run on record. "
            "Run pytest multiple times to populate the history view."
        )
    else:
        st.subheader("Pass Rate Over Time")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist_summaries["timestamp"],
            y=hist_summaries["pass_rate"],
            mode="lines+markers",
            line=dict(color=PRIMARY, width=3),
            marker=dict(size=12, color=PRIMARY),
            fill="tozeroy",
            fillcolor="rgba(0,51,102,0.08)",
            hovertemplate="<b>%{x|%d %b %Y, %H:%M}</b><br>"
                          "Pass Rate: %{y:.1f}%<extra></extra>",
        ))
        fig.update_layout(
            height=320, yaxis_range=[0, 105],
            yaxis_title="Pass Rate (%)", xaxis_title="",
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ----- Improved: dual-axis outcomes + pass-rate trend -----
        st.subheader("Test Outcomes per Run")

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Stacked outcome bars (left axis)
        fig.add_trace(
            go.Bar(
                x=hist_summaries["timestamp"],
                y=hist_summaries["passed"],
                name="Passed",
                marker_color=PASS_COLOR,
                hovertemplate="Passed: <b>%{y}</b><extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(
                x=hist_summaries["timestamp"],
                y=hist_summaries["failed"],
                name="Failed",
                marker_color=FAIL_COLOR,
                hovertemplate="Failed: <b>%{y}</b><extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(
                x=hist_summaries["timestamp"],
                y=hist_summaries["skipped"],
                name="Skipped",
                marker_color=SKIP_COLOR,
                hovertemplate="Skipped: <b>%{y}</b><extra></extra>",
            ),
            secondary_y=False,
        )

        # Pass rate trend line (right axis)
        fig.add_trace(
            go.Scatter(
                x=hist_summaries["timestamp"],
                y=hist_summaries["pass_rate"],
                name="Pass Rate",
                mode="lines+markers",
                line=dict(color=PRIMARY, width=2.5, dash="dot"),
                marker=dict(size=9, color=PRIMARY,
                            line=dict(color="white", width=2)),
                hovertemplate="Pass Rate: <b>%{y:.1f}%</b><extra></extra>",
            ),
            secondary_y=True,
        )

        fig.update_layout(
            barmode="stack",
            height=400,
            plot_bgcolor="white",
            margin=dict(l=20, r=20, t=30, b=60),
            hovermode="x unified",
            legend=dict(
                orientation="h", y=-0.2, x=0.5, xanchor="center",
                bgcolor="rgba(255,255,255,0.8)",
            ),
            xaxis=dict(
                showgrid=False,
                title="",
                tickformat="%d %b<br>%H:%M",
            ),
        )
        fig.update_yaxes(
            title_text="Tests", secondary_y=False,
            showgrid=True, gridcolor="#f1f5f9",
            rangemode="tozero",
        )
        fig.update_yaxes(
            title_text="Pass Rate (%)", secondary_y=True,
            range=[0, 105], showgrid=False,
            tickformat=".0f",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Run Log")
        table = hist_summaries.iloc[::-1].copy()
        table["When"] = table["timestamp"].apply(lambda d: format_datetime(d, True))
        table["Pass %"] = table["pass_rate"].round(1)
        table["Duration"] = table["duration"].apply(format_duration)
        st.dataframe(
            table[["When", "total", "passed", "failed", "skipped",
                   "Pass %", "Duration"]].rename(
                columns={
                    "total": "Total", "passed": "Passed",
                    "failed": "Failed", "skipped": "Skipped",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        # ----- Full audit PDF -----
        st.divider()
        st.subheader("History Report Scope")
        run_options = [
            r["timestamp"].strftime("%d %b %Y, %H:%M:%S")
            for _, r in hist_summaries.sort_values(
                "timestamp", ascending=False).iterrows()
        ]
        selected_runs = st.multiselect(
            "Runs to include",
            options=run_options,
            default=run_options[: min(5, len(run_options))],
            key="history_report_runs",
        )
        selected_run_times = set(selected_runs)
        history_tests = all_tests[
            all_tests["run_timestamp"].apply(
                lambda d: pd.Timestamp(d).strftime("%d %b %Y, %H:%M:%S")
            ).isin(selected_run_times)
        ].copy()
        history_summary = tests_summary(
            history_tests,
            timestamp=history_tests["run_timestamp"].max()
            if not history_tests.empty else datetime.now(),
            source="history",
        )
        try:
            history_pdf = generate_pdf_report(
                runs,
                history_summary,
                history_tests,
                report_title="T24 Test Automation - Run History Report",
                scope_label="Selected Runs",
            )
        except Exception:
            history_pdf = None

        adl1, adl2 = st.columns([1, 3])
        with adl1:
            render_pdf_bytes_download(
                history_pdf,
                key="pdf_dl_history",
                label="📄  Download History Report (PDF)",
                filename_prefix="BoK_T24_History_Report",
            )
        with adl2:
            st.caption(
                "Report for the selected historical runs, including KPIs, "
                "tier breakdown, per-test results, and failure forensics."
            )

# -------------------- TEST RUNNER --------------------
with tab_runner:
    st.subheader("Test Runner")
    st.caption(
        "Trigger pytest runs directly from the dashboard. Output streams "
        "below. The dashboard data refreshes automatically when each "
        "run completes - switch to **All Tests** to inspect results."
    )

    triggered = None

    # ----- Quick suites (marker-based, immune to file renames) -----
    st.markdown("##### Quick Suites")
    qr1, qr2, qr3, qr4 = st.columns(4)

    if qr1.button("🟢  Smoke", use_container_width=True):
        triggered = (["tests/smoke/"], "Smoke Suite")
    if qr2.button("🟡  Regression (all stable)", use_container_width=True):
        triggered = (
            ["tests/regression/", "-m", "not negative"],
            "Regression Suite",
        )
    if qr3.button(
        "🔵  Full E2E Lifecycle",
        use_container_width=True, type="primary",
    ):
        # Marker filter + ordering done by conftest priority hook.
        # Runs all E2E journeys, including Customer, Account, FT, and AA.
        triggered = (["tests/regression/", "-m", "e2e"], "Full E2E Lifecycle")
    if qr4.button("🟣  Everything", use_container_width=True):
        triggered = (["tests/"], "Full Suite")

    # ----- Individual journeys -----
    st.markdown("##### Individual Journeys")
    jr1, jr2, jr3, jr4 = st.columns(4)

    if jr1.button("👤  Customer (I/A)", use_container_width=True):
        triggered = (
            ["tests/regression/", "-k", "customer_input_authorise"],
            "Customer Lifecycle",
        )
    if jr2.button("💳  Account (I/A)", use_container_width=True):
        triggered = (
            ["tests/regression/", "-k",
             "open_current_account_input or account_open_authorise"],
            "Account Lifecycle",
        )
    if jr3.button("💸  Funds Transfer", use_container_width=True):
        triggered = (
            ["tests/regression/", "-k", "funds_transfer"],
            "Funds Transfer",
        )
    if jr4.button("🏦  AA Term Deposit", use_container_width=True):
        triggered = (
            ["tests/regression/test_07_aa_deposit_e2e.py"],
            "AA Term Deposit Lifecycle",
        )

    # ----- Compliance / negative -----
    st.markdown("##### Compliance & Negative Scenarios")
    nr1, nr2, nr3 = st.columns(3)

    if nr1.button("🚨  All Compliance Tests", use_container_width=True):
        triggered = (
            ["tests/regression/", "-m", "negative"],
            "Compliance Suite",
        )
    if nr2.button("MR + Female (headliner)", use_container_width=True):
        triggered = (
            ["tests/regression/", "-k", "title_mr_with_female"],
            "Title/Gender Compliance",
        )
    if nr3.button("Future DOB", use_container_width=True):
        triggered = (
            ["tests/regression/", "-k", "future_date_of_birth"],
            "Future DOB Compliance",
        )

    # ----- Performance / load testing -----
    st.markdown("##### Performance & Load Testing")
    st.caption(
        "Runs a separate Locust HTTP load probe against the selected T24 host. "
        "The default scenario is read-only and does not touch the Selenium "
        "functional automation."
    )

    default_host, default_path = default_perf_target()
    with st.expander("Configure Locust run", expanded=False):
        pc1, pc2 = st.columns([2, 1])
        with pc1:
            perf_host = st.text_input(
                "T24 host",
                value=default_host,
                help="Base URL only, for example http://host:port",
            )
            perf_paths_text = st.text_area(
                "Paths to probe",
                value=default_path,
                height=96,
                help="One path per line. Full URLs are accepted; only their path/query is used.",
            )
        with pc2:
            perf_users = st.number_input(
                "Virtual users", min_value=1, max_value=500, value=5, step=1
            )
            perf_spawn_rate = st.number_input(
                "Spawn rate / second",
                min_value=0.1,
                max_value=100.0,
                value=1.0,
                step=0.5,
            )
            perf_duration = st.text_input(
                "Duration", value="1m", help="Examples: 30s, 1m, 5m"
            )

        wc1, wc2, wc3 = st.columns(3)
        with wc1:
            perf_min_wait = st.number_input(
                "Min wait (sec)", min_value=0.0, max_value=60.0, value=1.0, step=0.5
            )
        with wc2:
            perf_max_wait = st.number_input(
                "Max wait (sec)", min_value=0.0, max_value=60.0, value=3.0, step=0.5
            )
        with wc3:
            perf_login_enabled = st.checkbox(
                "Submit login first",
                value=False,
                help="Use only in an approved performance environment.",
            )

        login_user = ""
        login_pass = ""
        login_path = "/BrowserWeb/servlet/BrowserLoginServlet"
        if perf_login_enabled:
            lc1, lc2, lc3 = st.columns([1, 1, 2])
            with lc1:
                login_user = st.text_input("Login user", value=os.getenv("PERF_LOGIN_USER", ""))
            with lc2:
                login_pass = st.text_input(
                    "Login password",
                    value=os.getenv("PERF_LOGIN_PASS", ""),
                    type="password",
                )
            with lc3:
                login_path = st.text_input(
                    "Login path",
                    value=os.getenv(
                        "PERF_LOGIN_PATH",
                        "/BrowserWeb/servlet/BrowserLoginServlet",
                    ),
                )

        perf_status_ph = st.empty()
        perf_log_ph = st.empty()
        if st.button("Run Read-Only Load Test", use_container_width=True):
            paths = [
                line.strip()
                for line in perf_paths_text.splitlines()
                if line.strip()
            ] or ["/"]
            if perf_max_wait < perf_min_wait:
                perf_status_ph.error("Max wait must be greater than or equal to min wait.")
            elif not Path(PERF_LOCUSTFILE).exists():
                perf_status_ph.error(f"Locust file not found: {PERF_LOCUSTFILE}")
            else:
                run_locust_headless(
                    {
                        "host": perf_host.rstrip("/"),
                        "paths": paths,
                        "users": int(perf_users),
                        "spawn_rate": float(perf_spawn_rate),
                        "duration": perf_duration.strip() or "1m",
                        "min_wait": float(perf_min_wait),
                        "max_wait": float(perf_max_wait),
                        "login_enabled": bool(perf_login_enabled),
                        "login_user": login_user,
                        "login_pass": login_pass,
                        "login_path": login_path,
                    },
                    perf_status_ph,
                    perf_log_ph,
                )
                st.cache_data.clear()

    perf_runs = latest_perf_runs()
    if perf_runs:
        selected_perf_run = st.selectbox(
            "Performance evidence",
            options=perf_runs,
            format_func=lambda p: p.name,
        )
        perf_stats = load_perf_stats(selected_perf_run)
        perf_failures = load_perf_failures(selected_perf_run)
        total = perf_total_row(perf_stats)

        pr1, pr2, pr3, pr4 = st.columns(4)
        pr1.metric(
            "Requests",
            format_perf_number(
                perf_value(total, "Request Count", "Requests", default=0),
                decimals=0,
            ),
        )
        pr2.metric(
            "Failures",
            format_perf_number(
                perf_value(total, "Failure Count", "Failures", default=0),
                decimals=0,
            ),
        )
        pr3.metric(
            "P95 Response",
            f"{format_perf_number(perf_value(total, '95%', '95', default=0), 0)} ms",
        )
        pr4.metric(
            "Throughput",
            f"{format_perf_number(perf_value(total, 'Requests/s', 'Req/s', default=0), 2)} req/s",
        )

        if not perf_stats.empty:
            st.dataframe(perf_stats, use_container_width=True, hide_index=True)
        if not perf_failures.empty:
            st.warning("Locust recorded failures for this run.")
            st.dataframe(perf_failures, use_container_width=True, hide_index=True)

        html_report = Path(selected_perf_run) / "report.html"
        if html_report.exists():
            with open(html_report, "rb") as f:
                st.download_button(
                    "Download Locust HTML Report",
                    data=f.read(),
                    file_name=f"{selected_perf_run.name}_locust_report.html",
                    mime="text/html",
                    use_container_width=True,
                )
    else:
        st.info("No performance runs yet. Configure Locust above and run a read-only probe when the T24 environment is ready.")

    # ----- Specific test file picker -----
    st.markdown("##### Pick Specific Test Files")
    available_files = discover_test_files()
    if not available_files:
        st.info("No test files discovered under tests/smoke/ or tests/regression/.")
    else:
        selected_files = st.multiselect(
            "Choose one or more test files to run",
            options=available_files,
        )
        if selected_files and st.button(
            f"▶  Run {len(selected_files)} selected file(s)",
            use_container_width=True,
        ):
            triggered = (selected_files, f"Custom ({len(selected_files)} files)")

    st.divider()

    status_placeholder = st.empty()
    log_placeholder = st.empty()

    if triggered:
        args, label = triggered
        run_pytest_streaming(args, label, status_placeholder, log_placeholder)
        st.info("💡  Switch to **All Tests** to inspect the new results.")

# -------------------- FOOTER --------------------
st.divider()
fcol1, fcol2 = st.columns([3, 1])
with fcol1:
    st.caption(
        "🏦 Bank of Kigali · T24 Test Automation Framework · "
        "Built by Inlaks Computers Limited"
    )
with fcol2:
    st.caption(
        f"<div style='text-align:right;'>"
        f"Generated {datetime.now().strftime('%d %b %Y, %H:%M')}"
        f"</div>",
        unsafe_allow_html=True,
    )
