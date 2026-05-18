import pytest
from pages.login_page import LoginPage
from utils.exceptions import T24TestError


@pytest.mark.smoke
def test_valid_login_lands_on_home_page(driver, config):
    """A user with valid credentials should reach the home page."""
    user = config["inputter"]["username"]
    home_page = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home_page.is_loaded():
        raise T24TestError(
            what_happened=f"Could not sign in to T24 as user '{user}'",
            why="The T24 home page did not appear after submitting credentials.",
            how_to_fix="Confirm the user exists, the password is correct, and "
                       "the T24 environment is reachable.",
        )


@pytest.mark.smoke
def test_login_page_shows_required_fields(driver, config):
    """Login page should expose username, password, and sign-in button."""
    login_page = LoginPage(driver).load(config["url"])

    missing = []
    if not login_page.is_visible(LoginPage.USERNAME_FIELD):
        missing.append("Username field")
    if not login_page.is_visible(LoginPage.PASSWORD_FIELD):
        missing.append("Password field")
    if not login_page.is_visible(LoginPage.SIGN_IN_BUTTON):
        missing.append("Sign-in button")

    if missing:
        raise T24TestError(
            what_happened="The T24 login page is incomplete",
            why=f"The following elements were not visible: {', '.join(missing)}.",
            how_to_fix="Check whether the BrowserWeb UI deployed correctly to this environment.",
        )