"""E2E test: Funds Transfer between accounts — INPUT only."""
import json
import logging
import os

import pytest

from pages.login_page import LoginPage
from pages.funds_transfer_page import FundsTransferPage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)

STATE_DIR = "reports/state"


@pytest.mark.e2e
def test_funds_transfer_input(driver, config):
    """INPUTTER books a funds transfer between two existing accounts."""

    debit_acct  = os.getenv("BW_FT_DEBIT_ACCOUNT")
    credit_acct = os.getenv("BW_FT_CREDIT_ACCOUNT")
    amount      = os.getenv("BW_FT_AMOUNT", "100")

    if not debit_acct or not credit_acct:
        raise T24TestError(
            what_happened="Funds Transfer test requires two live accounts",
            why="BW_FT_DEBIT_ACCOUNT and BW_FT_CREDIT_ACCOUNT not set in .env.",
            how_to_fix=(
                "Add to .env:\n"
                "  BW_FT_DEBIT_ACCOUNT=<existing authorised account no>\n"
                "  BW_FT_CREDIT_ACCOUNT=<existing authorised account no>\n"
                "  BW_FT_AMOUNT=100"
            ),
        )

    transfer = {
        "debit_account":    debit_acct,
        "credit_account":   credit_acct,
        "debit_amount":     amount,
    }
    logger.info(f"FT: {amount} from {debit_acct} to {credit_acct}")

    # PHASE 1 — Login
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened="Could not sign in as INPUTTER",
            why="Home page did not appear.",
            how_to_fix="Confirm INPUTTER credentials in .env.",
        )

    # PHASE 2 — Open FT form directly
    home.open_funds_transfer()
    home.switch_to_new_window()

    ft_page = FundsTransferPage(driver)
    ft_id_initial = ft_page.read_transaction_id()
    logger.info(f"FT form opened — initial transaction ID: {ft_id_initial}")

    # PHASE 3 — Fill
    ft_page.fill_transfer_form(transfer)
    ft_page.screenshot("01_ft_form_filled")

    # PHASE 4 — Validate
    ft_page.validate()
    ft_page.wait_for_transaction_result(timeout=5)
    ft_page.screenshot("02_ft_validated")

    if ft_page.has_overrides_popup():
        ft_page.screenshot("03_overrides_after_validate")
        ft_page.accept_overrides()
        ft_page.screenshot("04_overrides_accepted_validate")
        logger.info("Overrides accepted at validation stage")

    # PHASE 5 — Commit
    ft_page.commit()
    ft_page.wait_for_transaction_result(timeout=10)
    ft_page.screenshot("03_ft_committed")

    if ft_page.has_overrides_popup():
        ft_page.screenshot("06_overrides_after_commit")
        ft_page.accept_overrides()
        ft_page.wait_for_transaction_result(timeout=10)
        ft_page.screenshot("07_overrides_accepted_commit")
        logger.info("Overrides accepted at commit stage — transaction approved")

    result = ft_page.get_transaction_result()
    ft_page.screenshot("08_ft_final_result")
    if result["status"] != "success":
        raise T24TestError(
            what_happened=f"FT commit failed: {debit_acct} → {credit_acct}",
            why=f"T24 returned: {result['message']}",
            how_to_fix=(
                "Verify both accounts exist, are authorised, currencies are "
                "compatible, and the debit account has sufficient balance."
            ),
        )

    ft_id = result["transaction_id"] or ft_id_initial
    logger.info(f"✓ FT committed — transaction ID {ft_id}")

    # PHASE 6 — Persist state
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "last_ft.json"), "w") as f:
        json.dump({
            "ft_id":          ft_id,
            "debit_account":  debit_acct,
            "credit_account": credit_acct,
            "amount":         amount,
            "input_by":       config["inputter"]["username"],
        }, f, indent=2)

    logger.info(
        f"✓ Funds Transfer complete\n"
        f"   FT ID:    {ft_id}\n"
        f"   From:     {debit_acct}\n"
        f"   To:       {credit_acct}\n"
        f"   Amount:   {amount}\n"
        f"   Input by: {config['inputter']['username']}\n"
        f"   T24:      {result['message']}"
    )
