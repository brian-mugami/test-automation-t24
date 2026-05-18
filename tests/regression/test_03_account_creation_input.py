import json
import logging
import os

import pytest

from pages.login_page import LoginPage
from pages.current_account_page import CurrentAccountPage
from utils.exceptions import T24TestError
from utils.test_data import generate_account_data

logger = logging.getLogger(__name__)

STATE_FILE = "reports/state/last_customer.json"

@pytest.fixture(autouse=True)
def _require_customer_state():
    """Skip account tests if the customer state file is missing."""
    if not os.path.exists("reports/state/last_customer.json"):
        pytest.skip(
            "Account tests require an authorised customer. Run "
            "test_01_customer_creation_e2e.py first to produce "
            "reports/state/last_customer.json."
        )

@pytest.mark.regression
def test_open_current_account_input(driver, config):
    """Open a current account for the most recently created customer."""

    # Load the customer the previous test created
    if not os.path.exists(STATE_FILE):
        raise T24TestError(
            what_happened="No customer state found",
            why=f"Expected {STATE_FILE} (written by the customer E2E test) "
                f"but it does not exist.",
            how_to_fix="Run tests/regression/test_02_customer_creation_e2e.py "
                       "first to create a customer.",
        )

    with open(STATE_FILE) as f:
        customer = json.load(f)

    logger.info(
        f"Opening account for customer {customer['customer_no']} "
        f"({customer['gb_full_name']})"
    )

    account = generate_account_data(customer)
    logger.info(
        f"Account data: mnemonic={account['mnemonic']}, "
        f"title='{account['account_title']}', "
        f"short='{account['short_title']}'"
    )

    # ============================================================
    # PHASE 1 — Login as INPUTTER and open the form
    # ============================================================
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened=f"Could not sign in as INPUTTER "
                          f"'{config['inputter']['username']}'",
            why="T24 home page did not appear after login.",
            how_to_fix="Confirm INPUTTER credentials and T24 availability.",
        )

    home.open_current_account()
    home.switch_to_new_window()

    # ============================================================
    # PHASE 2 — Fill the form
    # ============================================================
    account_page = CurrentAccountPage(driver)
    account_page.fill_main_tab(account)
    account_page.screenshot("01_account_form_filled")

    # ============================================================
    # PHASE 3 — Validate
    # ============================================================
    account_page.validate()
    account_page.wait_for_transaction_result(timeout=5)
    account_page.screenshot("02_account_validated")

    # ============================================================
    # PHASE 4 — Commit
    # ============================================================
    account_page.commit()
    account_page.wait_for_transaction_result(timeout=10)
    account_page.screenshot("03_account_committed")

    result = account_page.get_transaction_result()
    if result["status"] != "success":
        raise T24TestError(
            what_happened=f"Account creation failed for customer "
                          f"{customer['customer_no']}",
            why=f"T24 returned: {result['message']}",
            how_to_fix=(
                "Check INPUTTER permissions on the ACCOUNT application and "
                "verify the customer record is in LIVE state (not still "
                "held for authorisation)."
            ),
        )

    account_id = result["transaction_id"]

    # ============================================================
    # PHASE 5 — Persist account state for the auth test
    # ============================================================
    state_dir = "reports/state"
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "last_account.json"), "w") as f:
        json.dump({
            "account_id":    account_id,
            "mnemonic":      account["mnemonic"],
            "account_title": account["account_title"],
            "short_title":   account["short_title"],
            "customer_no":   customer["customer_no"],
            "customer_name": customer["gb_full_name"],
            "input_by":      config["inputter"]["username"],
        }, f, indent=2)
    logger.info(f"💾 Account state saved → reports/state/last_account.json")

    logger.info(
        f"✓ Account INPUT complete\n"
        f"   Account ID:    {account_id}\n"
        f"   Mnemonic:      {account['mnemonic']}\n"
        f"   Title:         {account['account_title']}\n"
        f"   For customer:  {customer['customer_no']} ({customer['gb_full_name']})\n"
        f"   Held for:      authorisation\n"
        f"   T24 message:   {result['message']}"
    )