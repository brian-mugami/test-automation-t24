import os
import pytest
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import shutil
from datetime import datetime
from pathlib import Path

load_dotenv()

SCREENSHOT_DIR = Path("reports/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_DIR = Path("reports/history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def config():
    """Environment configuration loaded from .env."""
    cfg = {
        "url": os.getenv("BW_URL"),
        "inputter": {
            "username": os.getenv("BW_INPUTTER_USER") or os.getenv("BW_USER"),
            "password": os.getenv("BW_INPUTTER_PASS") or os.getenv("BW_PASS"),
        },
        "authoriser": {
            "username": os.getenv("BW_AUTHORISER_USER"),
            "password": os.getenv("BW_AUTHORISER_PASS"),
        },
    }
    if not cfg["url"]:
        pytest.fail("Missing BW_URL in .env")
    if not cfg["inputter"]["username"]:
        pytest.fail("Missing BW_INPUTTER_USER (or legacy BW_USER) in .env")
    return cfg


@pytest.fixture
def driver():
    """Fresh Chrome driver per test. Closes automatically after."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--ignore-certificate-errors")
    # Remove this line if you want browser to close after each test
    # options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    yield driver
    driver.quit()


# ---------- Screenshot on failure ----------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture a screenshot whenever a test fails."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        driver = item.funcargs.get("driver")
        if driver:
            test_name = item.name.replace("/", "_")
            path = SCREENSHOT_DIR / f"FAIL_{test_name}.png"
            driver.save_screenshot(str(path))
            print(f"Screenshot saved: {path}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshots: failures always, successes for regression/e2e tests."""
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    driver = item.funcargs.get("driver")
    if not driver:
        return

    test_name = item.name.replace("/", "_")

    if report.failed:
        path = SCREENSHOT_DIR / f"FAIL_{test_name}.png"
        driver.save_screenshot(str(path))
        print(f"Failure screenshot: {path}")

    elif report.passed:
        # Capture final-state screenshots for regression and e2e —
        # tests where the end state is meaningful evidence
        markers = {m.name for m in item.iter_markers()}
        if markers & {"regression", "e2e"}:
            path = SCREENSHOT_DIR / f"PASS_{test_name}.png"
            driver.save_screenshot(str(path))
            print(f"Success screenshot: {path}")


def pytest_unconfigure(config):
    """Archive the JSON report to history after the run completes.

    This builds the trail the dashboard reads to show history."""
    source = Path("reports/report.json")
    if not source.exists():
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destination = HISTORY_DIR / f"run-{timestamp}.json"
    shutil.copy(source, destination)
    print(f"\n[Archived] Run JSON saved to: {destination}")

def pytest_collection_modifyitems(config, items):
    """Enforce dependency order for the I/A lifecycle tests.

    Customer must be input AND authorised before any account test runs
    (the account tests read reports/state/last_customer.json).
    """
    priority = {
        # Smoke first
        "test_login": 10,
        "test_logout": 11,
        "test_open_current_account_navigation": 12,
        # Customer lifecycle
        "test_customer_input_authorise_lifecycle": 20,
        # Account lifecycle (depends on customer state)
        "test_open_current_account_input": 30,
        "test_account_open_authorise_lifecycle": 31,
        # Negative scenarios last (designed to fail)
        "test_funds_transfer_input": 40,
        "test_aa_term_deposit_input": 50,
        "test_compliance_": 90,
        "test_negative_": 91,
    }

    def sort_key(item):
        for name_pattern, prio in priority.items():
            if name_pattern in item.nodeid:
                return prio
        return 50  # unmatched tests run in the middle

    items.sort(key=sort_key)
