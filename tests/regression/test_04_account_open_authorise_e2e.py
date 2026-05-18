import json
import logging
import os

import pytest
from selenium.common.exceptions import NoSuchElementException

from pages.login_page import LoginPage
from pages.current_account_page import CurrentAccountPage
from pages.account_auth_list_page import AccountAuthListPage
from utils.exceptions import T24TestError
from utils.test_data import generate_account_data

logger = logging.getLogger(__name__)

STATE_DIR = "reports/state"
CUSTOMER_STATE = os.path.join(STATE_DIR, "last_customer.json")

@pytest.fixture(autouse=True)
def _require_customer_state():
    """Skip account tests if the customer state file is missing."""
    if not os.path.exists("reports/state/last_customer.json"):
        pytest.skip(
            "Account tests require an authorised customer. Run "
            "test_01_customer_creation_e2e.py first to produce "
            "reports/state/last_customer.json."
        )

@pytest.mark.e2e
def test_account_open_authorise_lifecycle(driver, config):
    """Open a current account for an existing customer, then authorise it."""

    if not os.path.exists(CUSTOMER_STATE):
        raise T24TestError(
            what_happened="No customer state found",
            why=f"Expected {CUSTOMER_STATE} (written by the customer E2E test).",
            how_to_fix="Run test_customer_input_authorise_lifecycle first.",
        )

    with open(CUSTOMER_STATE) as f:
        customer = json.load(f)

    account = generate_account_data(customer)
    logger.info(
        f"Opening account for customer {customer['customer_no']} "
        f"({customer['gb_full_name']}) — mnemonic {account['mnemonic']}"
    )

    # ============================================================
    # PHASE 1 — INPUT as INPUTTER
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
            why="The T24 home page did not appear after login.",
            how_to_fix="Confirm INPUTTER credentials and T24 availability.",
        )

    home.open_current_account()
    home.switch_to_new_window()

    account_page = CurrentAccountPage(driver)
    account_page.fill_main_tab(account)
    account_page.screenshot("01_account_form_filled")

    account_page.validate()
    account_page.wait_for_transaction_result(timeout=5)
    account_page.screenshot("02_account_validated")

    account_page.commit()
    account_page.wait_for_transaction_result(timeout=10)
    account_page.screenshot("03_account_committed")

    input_result = account_page.get_transaction_result()
    if input_result["status"] != "success":
        raise T24TestError(
            what_happened=f"Account INPUT failed for customer "
                          f"{customer['customer_no']}",
            why=f"T24 returned: {input_result['message']}",
            how_to_fix="Check INPUTTER permissions on ACCOUNT and customer status.",
        )

    account_id = input_result["transaction_id"]
    logger.info(f"✓ INPUT complete — account {account_id} held for authorisation")

    # ============================================================
    # PHASE 2 — Close account window, logout INPUTTER
    # ============================================================
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    home.logout()
    home.screenshot("04_inputter_signed_off")

    # ============================================================
    # PHASE 3 — Login as AUTHORISER
    # ============================================================
    auth_user = config["authoriser"]["username"]
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["authoriser"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened=f"Could not sign in as AUTHORISER '{auth_user}'",
            why="The T24 home page did not appear after login.",
            how_to_fix="Confirm BW_AUTHORISER_USER and BW_AUTHORISER_PASS in .env.",
        )
    home.screenshot("05_authoriser_signed_in")

    # ============================================================
    # PHASE 4 — Open the account auth queue
    # ============================================================
    home.open_account_auth_queue()
    home.switch_to_new_window()

    auth_list = AccountAuthListPage(driver)
    auth_list.screenshot("06_account_auth_queue_loaded")

    pending = auth_list.list_pending_account_ids()
    logger.info(f"Auth queue contains {len(pending)} pending account(s)")

    if account_id not in pending:
        raise T24TestError(
            what_happened=f"Account {account_id} not found in the auth queue",
            why=(
                f"The queue lists {len(pending)} pending record(s) but our "
                f"account ({account_id}) is not among them."
            ),
            how_to_fix=(
                "Check the AUTHORISER user's enquiry filters in T24. The "
                "account should be visible to any user with AUTH rights "
                "on ACCOUNT."
            ),
        )

    # ============================================================
    # PHASE 5 — Drill down into the account record
    # ============================================================
    try:
        auth_list.click_authorise_for(account_id)
    except NoSuchElementException as e:
        raise T24TestError(
            what_happened=f"Could not drill down into account {account_id}",
            why=str(e),
            how_to_fix=(
                "The account may have been authorised by another user "
                "between the queue check and the click."
            ),
        )

    auth_page = CurrentAccountPage(driver)
    auth_page.wait_for_record_loaded()
    auth_page.scroll_to_toolbar_authorise()
    auth_page.screenshot("07_account_open_with_toolbar")

    # ============================================================
    # PHASE 6 — Authorise
    # ============================================================
    auth_page.authorise()
    auth_page.wait_for_transaction_result(timeout=10)
    auth_page.screenshot("08_authorise_attempted")

    auth_result = auth_page.get_transaction_result()
    if auth_result["status"] != "success":
        raise T24TestError(
            what_happened=f"AUTHORISE phase failed for account {account_id}",
            why=f"T24 returned: {auth_result['message']}",
            how_to_fix=(
                f"Confirm '{auth_user}' has AUTH rights on ACCOUNT. T24's "
                "segregation of duties requires a DIFFERENT user from the "
                "one who created the record."
            ),
        )

    # ============================================================
    # PHASE 7 — Persist account state
    # ============================================================
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "last_account.json"), "w") as f:
        json.dump({
            "account_id":    account_id,
            "mnemonic":      account["mnemonic"],
            "account_title": account["account_title"],
            "short_title":   account["short_title"],
            "customer_no":   customer["customer_no"],
            "customer_name": customer["gb_full_name"],
            "input_by":      config["inputter"]["username"],
            "authorised_by": auth_user,
        }, f, indent=2)

    logger.info(
        f"✓ Full account I/A lifecycle complete\n"
        f"   Account ID:    {account_id}\n"
        f"   Mnemonic:      {account['mnemonic']}\n"
        f"   Title:         {account['account_title']}\n"
        f"   For customer:  {customer['customer_no']} ({customer['gb_full_name']})\n"
        f"   Input by:      {config['inputter']['username']}\n"
        f"   Authorised by: {auth_user}\n"
        f"   Final state:   LIVE\n"
        f"   T24 message:   {auth_result['message']}"
    )
    auth_page.screenshot("09_account_live")