import json
import logging
import os
import time

import pytest

from pages.login_page import LoginPage
from pages.aa_product_catalog_page import AAProductCatalogPage
from pages.aa_term_deposit_page import AATermDepositPage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)

STATE_DIR = "reports/state"


def _switch_to_newest_window(driver, before_handles):
    """If a new window appeared, switch to it and maximise. Returns bool."""
    new = [h for h in driver.window_handles if h not in before_handles]
    if new:
        driver.switch_to.window(new[-1])
        try:
            driver.maximize_window()
        except Exception:
            pass
        return True
    return False


@pytest.mark.e2e
def test_aa_term_deposit_input(driver, config):
    """INPUTTER creates and commits an AA Term Deposit arrangement."""

    customer = os.getenv("BW_AA_CUSTOMER", "190598")
    currency = os.getenv("BW_AA_CURRENCY", "USD")
    account  = os.getenv("BW_AA_ACCOUNT", "125539")
    logger.info(f"AA Term Deposit: customer={customer}, currency={currency}, "
                f"settlement account={account}")

    # PHASE 1 - Login as INPUTTER
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened="Could not sign in as INPUTTER",
            why="Home page did not appear after login.",
            how_to_fix="Confirm INPUTTER credentials in .env.",
        )
    logger.info("Logged in - home page loaded")

    # PHASE 2 - Navigate the Product Catalog to a New Arrangement
    h0 = set(driver.window_handles)
    home.open_aa_product_catalog()
    time.sleep(2)
    _switch_to_newest_window(driver, h0)

    catalog = AAProductCatalogPage(driver)
    catalog.wait_for_catalog_loaded()
    catalog.screenshot("01_aa_product_catalog")

    catalog.open_group("Deposits", "Term Deposits")
    h1 = set(driver.window_handles)
    catalog.drilldown_item("Term Deposits")
    time.sleep(2)
    _switch_to_newest_window(driver, h1)
    catalog.wait_for_products_screen()
    catalog.screenshot("02_aa_term_deposit_products")

    h2 = set(driver.window_handles)
    catalog.click_new_arrangement()
    time.sleep(2)
    _switch_to_newest_window(driver, h2)

    # PHASE 3 - Fill the AA arrangement form
    aa = AATermDepositPage(driver)
    aa.wait_for_form_loaded()
    aa.screenshot("03_aa_input_form")

    aa.fill_initial_fields(customer=customer, currency=currency)
    aa.screenshot("04_aa_header_filled")

    # First validation - reveals the settlement (pay-in / pay-out) fields
    aa.validate()
    aa.wait_for_settlement_fields()
    aa.screenshot("05_aa_validated_settlement_fields")

    aa.fill_settlement_accounts(payin=account, payout=account)
    aa.screenshot("06_aa_settlement_filled")

    # Second validation
    aa.validate()
    time.sleep(2)
    aa.screenshot("07_aa_revalidated")

    # PHASE 4 - Commit
    aa.screenshot("08_aa_before_commit")
    aa.commit()
    aa.screenshot("09_aa_commit_clicked")  # post-commit: warning / override stage

    answered = aa.answer_warnings(answer="RECEIVED")
    logger.info(f"Commit-time warnings answered: {answered}")
    aa.screenshot("10_aa_warning_answered")

    if aa.has_overrides_popup():
        aa.screenshot("11_aa_override_prompt")  # the override, before accepting
        aa.accept_overrides()
        aa.screenshot("12_aa_override_accepted")
        logger.info("Overrides accepted - commit finalised")

        # Defensive: commitOverrides() can surface a further override round.
        extra = 0
        while extra < 2 and aa.has_overrides_popup(wait_seconds=6):
            extra += 1
            aa.accept_overrides()
        if extra:
            logger.info(f"Accepted {extra} further override round(s)")
            aa.screenshot("12_aa_override_accepted")
    else:
        logger.info("No override prompt appeared after commit")

    # PHASE 5 - Capture the arrangement reference
    arrangement_id = aa.read_arrangement_id()
    aa.screenshot("13_aa_committed_final")

    if not arrangement_id:
        raise T24TestError(
            what_happened="AA arrangement committed but no reference captured",
            why=("read_arrangement_id scanned every window and frame but the "
                 "ARRANGEMENT field never resolved past 'NEW'."),
            how_to_fix=("Review 13_aa_committed_final.png. If the arrangement "
                        "reference IS visible on screen, send that screenshot "
                        "so the locator can be adjusted."),
        )
    logger.info(f"AA Term Deposit committed - arrangement ID {arrangement_id}")

    # PHASE 6 - Persist state for the authorise phase
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "last_aa.json"), "w") as f:
        json.dump({
            "arrangement_id": arrangement_id,
            "customer": customer,
            "currency": currency,
            "settlement_account": account,
            "input_by": config["inputter"]["username"],
        }, f, indent=2)

    logger.info(
        f"AA Term Deposit input complete\n"
        f"   Arrangement: {arrangement_id}\n"
        f"   Customer:    {customer}\n"
        f"   Currency:    {currency}\n"
        f"   Account:     {account}\n"
        f"   Input by:    {config['inputter']['username']}"
    )