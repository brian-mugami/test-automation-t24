"""Navigation tests for the Customer application."""
import pytest
from selenium.common.exceptions import TimeoutException

from pages.login_page import LoginPage
from utils.exceptions import T24TestError


@pytest.mark.smoke
def test_navigate_to_individual_customer_screen(driver, config):
    """A user can reach the Individual Customer creation screen from the home page."""
    user = config["inputter"]["username"]

    # ---------- Step 1: sign in ----------
    home_page = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )

    if not home_page.is_loaded():
        raise T24TestError(
            what_happened=f"Could not sign in to T24 as '{user}'",
            why="The home page did not appear after submitting credentials.",
            how_to_fix="Confirm the user exists, the password is correct, "
                       "and the T24 environment is reachable.",
        )

    # ---------- Step 2: open Individual Customer ----------
    home_page.open_individual_customer_by_command()

    try:
        home_page.switch_to_new_window()
    except TimeoutException:
        raise T24TestError(
            what_happened="The Individual Customer creation screen did not open",
            why="After requesting the customer creation function, no new T24 "
                "window appeared within the expected time.",
            how_to_fix=f"Verify that user '{user}' has access to the CUSTOMER "
                       "application in T24 security settings.",
        )

    home_page.screenshot("individual_customer_screen_opened")