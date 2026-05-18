"""E2E test: full customer Input → Authorise lifecycle.

Demonstrates T24's dual-control segregation-of-duties pattern:
- INPUTTER user creates and commits a customer record (held in IHLD state)
- AUTHORISER user finds the record in the auth queue and authorises it

Produces 12 screenshots documenting every state transition — a complete
audit trail for release-readiness evidence.
"""
import logging
import pytest

from selenium.common.exceptions import NoSuchElementException

from pages.login_page import LoginPage
from pages.individual_customer_page import IndividualCustomerPage
from pages.customer_auth_list_page import CustomerAuthListPage
from utils.exceptions import T24TestError
from utils.test_data import generate_customer_data

logger = logging.getLogger(__name__)
import json, os

state_dir = "reports/state"
state_path = os.path.join(state_dir, "last_customer.json")

state_dir = "reports/state"
os.makedirs(state_dir, exist_ok=True)


@pytest.mark.e2e
def test_customer_input_authorise_lifecycle(driver, config):
    """Customer created by INPUTTER → authorised by AUTHORISER."""
    customer = generate_customer_data(title="Mr")

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
            why="The T24 home page did not appear after submitting credentials.",
            how_to_fix="Confirm INPUTTER credentials and T24 availability.",
        )

    home.open_individual_customer_by_command()
    home.switch_to_new_window()  # → customer creation window

    customer_page = IndividualCustomerPage(driver)
    mnemonic = customer_page.build_mnemonic(customer)
    logger.info(
        f"Creating customer: {customer['gb_full_name']} "
        f"(mnemonic {mnemonic})"
    )

    customer_page.fill_customer_tab(customer)
    customer_page.screenshot("01_customer_tab_filled")
    customer_page.fill_physical_address_tab(customer)
    customer_page.screenshot("02_physical_address_filled")
    customer_page.fill_contact_details_tab(customer)
    customer_page.screenshot("03_contact_details_filled")

    customer_page.validate()
    customer_page.wait_for_transaction_result(timeout=5)
    customer_page.screenshot("04_validation_done")

    customer_page.commit()
    customer_page.wait_for_transaction_result(timeout=10)
    customer_page.screenshot("05_commit_success")

    input_result = customer_page.get_transaction_result()
    if input_result["status"] != "success":
        raise T24TestError(
            what_happened=f"INPUT phase failed for '{customer['gb_full_name']}'",
            why=f"T24 returned: {input_result['message']}",
            how_to_fix="See INPUTTER permissions or field validations.",
        )

    record_id = input_result["transaction_id"]
    logger.info(f"✓ INPUT complete — record {record_id} held for authorisation")

    # ============================================================
    # PHASE 2 — DERIVE THE CUSTOMER NUMBER
    # ============================================================
    # The mnemonic is "M" + customer_no by construction. Stripping the
    # leading "M" gives us the customer number that appears in the
    # auth queue's first column. We assert it matches the parsed
    # transaction_id as a sanity check.
    assert mnemonic.startswith("M"), f"Expected mnemonic to start with 'M', got '{mnemonic}'"
    customer_no = mnemonic[1:]
    assert customer_no == record_id, (
        f"Mnemonic-derived customer_no '{customer_no}' does not match "
        f"transaction_id '{record_id}'"
    )
    logger.info(f"Customer number derived from mnemonic: {customer_no}")

    # ============================================================
    # PHASE 3 — CLOSE CUSTOMER WINDOW AND LOG OUT INPUTTER
    # ============================================================
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    home.logout()
    home.screenshot("06_inputter_signed_off")

    # ============================================================
    # PHASE 4 — LOG IN AS AUTHORISER
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
            why="The T24 home page did not appear after submitting credentials.",
            how_to_fix="Confirm BW_AUTHORISER_USER and BW_AUTHORISER_PASS in .env.",
        )
    home.screenshot("07_authoriser_signed_in")

    # ============================================================
    # PHASE 5 — OPEN THE AUTHORISATION QUEUE
    # ============================================================
    home.open_customer_auth_queue()
    home.switch_to_new_window()

    auth_list = CustomerAuthListPage(driver)
    auth_list.screenshot("08_auth_queue_loaded")


    pending = auth_list.list_pending_ids()
    logger.info(f"Auth queue contains {len(pending)} pending record(s)")

    if customer_no not in pending:
        raise T24TestError(
            what_happened=f"Customer {customer_no} not found in the authorisation queue",
            why=(
                f"The queue lists {len(pending)} pending record(s) but our "
                f"record ({customer_no}) is not among them."
            ),
            how_to_fix=(
                "Check the AUTHORISER user's enquiry filters in T24. The "
                "record should be visible to any user with AUTH rights "
                "on CUSTOMER."
            ),
        )

    # ============================================================
    # PHASE 6 — DRILL DOWN INTO THE RECORD
    # ============================================================

    try:
        auth_list.click_authorise_for(customer_no)
    except NoSuchElementException as e:
        raise T24TestError(
            what_happened=f"Could not drill down into record {customer_no}",
            why=str(e),
            how_to_fix=(
                "The record may have been authorised by another user "
                "between the queue check and the click. Re-run to retry."
            ),
        )

    auth_page = IndividualCustomerPage(driver)
    auth_page.wait_for_record_loaded()
    auth_page.scroll_to_toolbar_authorise()
    auth_page.screenshot("09_record_open_with_toolbar")

    # ============================================================
    # PHASE 7 — AUTHORISE
    # ============================================================
    auth_page.authorise()
    auth_page.wait_for_transaction_result(timeout=10)
    auth_page.screenshot("10_authorise_attempted")

    auth_result = auth_page.get_transaction_result()
    if auth_result["status"] != "success":
        raise T24TestError(
            what_happened=f"AUTHORISE phase failed for record {customer_no}",
            why=f"T24 returned: {auth_result['message']}",
            how_to_fix=(
                f"Confirm '{auth_user}' has AUTH rights on CUSTOMER. T24's "
                "segregation of duties requires a DIFFERENT user from the "
                "one who created the record."
            ),
        )

    logger.info(
        f"✓ Full I/A lifecycle complete\n"
        f"   Customer:      {customer['gb_full_name']}\n"
        f"   Customer no:   {customer_no}\n"
        f"   Mnemonic:      {mnemonic}\n"
        f"   Input by:      {config['inputter']['username']}\n"
        f"   Authorised by: {auth_user}\n"
        f"   Final state:   LIVE\n"
        f"   T24 message:   {auth_result['message']}"
    )
    with open(state_path, "w") as f:
        json.dump({
            "customer_no": customer_no,
            "mnemonic": mnemonic,
            "given_name": customer["given_name"],
            "family_name": customer["family_name"],
            "gb_full_name": customer["gb_full_name"],
            "gb_short_name": customer["gb_short_name"],
            "input_by": config["inputter"]["username"],
            "authorised_by": auth_user,
        }, f, indent=2)
    logger.info(f"💾 Customer state saved → {state_path}")
    auth_page.screenshot("11_record_live")

