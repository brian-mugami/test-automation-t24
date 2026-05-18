"""Smoke test: navigation to the Open Current Account form.

Verifies the docommand routing and form loading without filling
anything. If this fails, the regression and E2E account tests
have no chance of passing — fast canary.
"""
import logging
import pytest

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from pages.login_page import LoginPage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


@pytest.mark.smoke
def test_open_current_account_form_loads(driver, config):
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

    home.open_current_account()
    home.switch_to_new_window()

    # Wait for the CA.OPEN form's mandatory CUSTOMER field
    customer_field = (By.ID, "fieldName:CUSTOMER")
    category_field = (By.ID, "fieldName:CATEGORY")
    currency_field = (By.ID, "fieldName:CURRENCY")

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.find_element(*customer_field).is_displayed()
        )
    except Exception:
        driver.save_screenshot("reports/screenshots/DEBUG_caopen_not_loaded.png")
        raise T24TestError(
            what_happened="Open Current Account form did not load",
            why=(
                "Expected fieldName:CUSTOMER to be visible within 20s "
                "after the ACCOUNT,CA.OPEN docommand. Saved "
                "DEBUG_caopen_not_loaded.png for inspection."
            ),
            how_to_fix=(
                "Verify the INPUTTER user has access to ACCOUNT,CA.OPEN "
                "in T24. Check the menu manually for the Account → Open "
                "Current Account path."
            ),
        )

    # Verify the other mandatory fields are present and pre-filled correctly
    category_value = driver.find_element(*category_field).get_attribute("value")
    currency_value = driver.find_element(*currency_field).get_attribute("value")

    logger.info(
        f"✓ Open Current Account form loaded successfully\n"
        f"   Form: ACCOUNT / CA.OPEN (INPUT)\n"
        f"   Customer ID field:  present, empty (awaiting input)\n"
        f"   Product Code:       pre-filled as '{category_value}' (Current Account)\n"
        f"   Currency:           pre-filled as '{currency_value}'"
    )

    # Take a clean screenshot of the empty form for the demo evidence pack
    driver.save_screenshot("reports/screenshots/PASS_caopen_form_loaded.png")

    assert category_value == "1001", f"Expected CATEGORY=1001, got '{category_value}'"
    assert currency_value == "USD", f"Expected CURRENCY=USD, got '{currency_value}'"