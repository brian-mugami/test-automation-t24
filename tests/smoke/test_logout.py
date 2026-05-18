"""Smoke test for the logout flow."""
import pytest
from pages.login_page import LoginPage
from utils.exceptions import T24TestError


@pytest.mark.smoke
def test_user_can_sign_off(driver, config):
    """A signed-in user can sign off and return to the login screen."""
    user = config["inputter"]["username"]

    home_page = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )

    if not home_page.is_loaded():
        raise T24TestError(
            what_happened=f"Pre-condition failed — could not sign in as '{user}'",
            why="The T24 home page did not appear after submitting credentials, "
                "so we couldn't proceed to test sign-off.",
            how_to_fix="Confirm the user account is active, the password is current, "
                       "and the T24 environment is reachable.",
        )

    home_page.logout()

    # After logout, the login page should be visible again
    login_page = LoginPage(driver)
    if not login_page.is_visible(LoginPage.USERNAME_FIELD):
        raise T24TestError(
            what_happened="Sign-off did not return the user to the login screen",
            why="After clicking Sign Off, the username field on the login page "
                "did not reappear within the expected time.",
            how_to_fix="Check whether the SIGN.OFF command is enabled for this "
                       "T24 environment, or whether the sign-off button has changed.",
        )