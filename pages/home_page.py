"""T24 BrowserWeb home page (post-login landing)."""
import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    """Page object for the T24 landing page after successful sign-in."""

    # Login field that should disappear once we're past the sign-in screen
    FRAMESET = (By.TAG_NAME, "frameset")
    BANNER_FRAME = (By.CSS_SELECTOR, "frame[id^='banner']")
    MENU_FRAME = (By.CSS_SELECTOR, "frame[id^='menu']")
    MENU_PANE = (By.ID, "pane_")
    SIGN_OFF_BUTTON = (
        By.XPATH,
        "//a[contains(@onclick, \"docommand('SIGN.OFF')\")]"
    )

    def open_aa_product_catalog(self) -> "HomePage":
        return self.execute_command("COS AA.PRODUCT.CATALOG.RETAIL")

    def open_account_transfer(self) -> "HomePage":
        """Open the Account Transfer chooser via 'COS ACCOUNT.TRANSFER'."""
        return self.execute_command("COS ACCOUNT.TRANSFER")

    def open_funds_transfer_auth_queue(self) -> "HomePage":
        return self.execute_command("COS FUNDS.TRANSFER$NAU,ACTR.FTHP")
    def open_current_account(self):
        return self.execute_command("ACCOUNT,CA.OPEN I F3")

    def open_funds_transfer(self) -> "HomePage":
        return self.execute_command("FUNDS.TRANSFER,ACTR.FTHP I F3")

    def open_account_auth_queue(self):
        """Open the Authorise/Delete Account enquiry (COS ACCOUNT.NAU)."""
        return self.execute_command("COS ACCOUNT.NAU")


    def is_loaded(self, login_url: str = None) -> bool:
        try:
            self.wait.until(lambda d: self.is_present(self.FRAMESET, timeout=1))
            if not self.is_present(self.BANNER_FRAME):
                return False
            if not self.is_present(self.MENU_FRAME):
                return False
            with self.in_frame(self.MENU_FRAME):
                return self.is_present(self.MENU_PANE)

        except TimeoutException:
            return False

    # ---------- Menu navigation ----------
    @staticmethod
    def _menu_item_locator(text: str) -> tuple:
        return (
            By.XPATH,
            f"//span[normalize-space(text())='{text}'] | "
            f"//a[normalize-space(text())='{text}']"
        )

    def click_menu_item(self, text: str) -> "HomePage":
        """Click a single menu item by its visible label, inside the menu frame."""
        # Caller is responsible for already being inside the menu frame
        locator = self._menu_item_locator(text)
        self.click(locator)
        return self

    def navigate_menu(self, *menu_path: str) -> "HomePage":
        """Walk a menu path, clicking each item in order.

        Example:
            home_page.navigate_menu('User Menu', 'Customer', 'Individual Customer')
        """
        with self.in_frame(self.MENU_FRAME):
            for item in menu_path:
                self.click_menu_item(item)
        return self

    def open_customer_auth_queue(self) -> "HomePage":
        return self.execute_command("COS CUSTOMER.NAU")

    # ---------- Convenience methods for known journeys ----------
    def open_individual_customer(self):
        """Navigate: User Menu → Customer → Individual Customer.

        Opens the customer creation window. Returns when the click is dispatched;
        switching to the new window is handled by the caller / next page object.
        """
        return self.navigate_menu("User Menu", "Customer", "Individual Customer")

    def execute_command(self, command: str) -> "HomePage":
        with self.in_frame(self.MENU_FRAME):
            self.driver.execute_script(f"docommand('{command}');")
        return self

    def open_individual_customer_by_command(self):
        """Open the Individual Customer screen via the T24 command API."""
        return self.execute_command("CUSTOMER,INPUT I F3")

    # def logout(self) -> None:
    #     """Sign out via the banner's Sign Off button. Returns to the login page."""
    #     self.switch_to_frame(self.BANNER_FRAME)
    #     self.click(self.SIGN_OFF_BUTTON)
    #     self.switch_to_default()
    #     # After sign-off, T24 reloads to the login page (no frameset)
    #     self.wait.until(lambda d: self.is_present(
    #         (By.ID, "signOnName"), timeout=10
    #     ))
    #     logger.info("User signed off successfully")

    def logout(self) -> None:
        # 1. Click Sign Off (in the banner frame)
        self.switch_to_frame(self.BANNER_FRAME)
        self.js_click(self.SIGN_OFF_BUTTON)
        self.switch_to_default()

        # 2. Accept any confirmation alert that may appear
        try:
            WebDriverWait(self.driver, 3).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            logger.info(f"Logout confirmation alert: '{alert.text}' — accepting")
            alert.accept()
        except TimeoutException:
            logger.info("No confirmation alert appeared, continuing")

        # 3. Wait for the login page to reappear
        try:
            self.wait.until(lambda d: self.is_present(
                (By.ID, "signOnName"), timeout=10
            ))
            logger.info("Logout successful — login page visible")
        except TimeoutException:
            self.screenshot("logout_failure_state")
            raise
