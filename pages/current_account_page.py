"""T24 Account application — CA.OPEN (Open Current Account, INPUT version)."""
import logging
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


class CurrentAccountPage(BasePage):
    """Open Current Account form (ACCOUNT / CA.OPEN, INPUT version).

    Same structural patterns as IndividualCustomerPage — single main
    tab, validate/commit via toolbar accesskeys, transaction result
    parsed from td.message.
    """

    # ---------- Mandatory & key main-tab fields ----------
    CUSTOMER = (By.ID, "fieldName:CUSTOMER")
    CATEGORY = (By.ID, "fieldName:CATEGORY")
    CURRENCY = (By.ID, "fieldName:CURRENCY")
    MNEMONIC = (By.ID, "fieldName:MNEMONIC")
    ACCOUNT_TITLE_1 = (By.ID, "fieldName:ACCOUNT.TITLE.1:1")
    SHORT_TITLE = (By.ID, "fieldName:SHORT.TITLE:1")

    # ---------- Toolbar buttons ----------
    VALIDATE_BUTTON = (By.XPATH, "//a[@accesskey='V']")
    COMMIT_BUTTON = (By.XPATH, "//a[@accesskey='C']")
    TOOLBAR_AUTHORISE = (
        By.XPATH,
        "//a[@accesskey='A' and @title='Authorises a deal']"
    )
    AUTHORISE_BUTTON = TOOLBAR_AUTHORISE  # backward-compat alias

    # ---------- Transaction result detection ----------
    TXN_MESSAGE = (By.CSS_SELECTOR, "td.message")
    ERROR_PAGE_CAPTION = (
        By.XPATH,
        "//td[@class='caption' and contains(text(), 'Error Message')]"
    )
    ERROR_HIDDEN_INPUT = (By.ID, "errorMessageFromT24")

    def wait_for_record_loaded(self, timeout: int = 30) -> None:
        """Wait for the account view to render after a drilldown click."""
        time.sleep(2)
        end = time.time() + timeout
        while time.time() < end:
            if self._find_toolbar_frame():
                logger.info("✓ Account record loaded — toolbar Authorise reachable")
                return
            time.sleep(1)

        self.driver.switch_to.default_content()
        self.screenshot("DEBUG_account_record_not_loaded")
        raise T24TestError(
            what_happened="Account record did not load after drilldown",
            why=(
                f"Searched every frame for the toolbar Authorise button for "
                f"{timeout}s but never found it. Saved "
                "DEBUG_account_record_not_loaded.png for inspection."
            ),
            how_to_fix=(
                "Open the DEBUG screenshot. If the record IS visible, the "
                "toolbar is in an unexpected DOM location. If not, the "
                "drilldown click did not fire."
            ),
        )

    def scroll_to_toolbar_authorise(self) -> None:
        """Scroll the toolbar Authorise into view for the screenshot."""
        if not self._is_toolbar_present():
            self._find_toolbar_frame()
        try:
            btn = self.driver.find_element(*self.TOOLBAR_AUTHORISE)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", btn
            )
            time.sleep(0.5)
            logger.info("Scrolled toolbar Authorise into view")
        except NoSuchElementException:
            logger.warning("Toolbar Authorise not found for scroll")

    def authorise(self) -> None:
        """Click the toolbar Authorise button (native click for reliability)."""
        if not self._is_toolbar_present():
            if not self._find_toolbar_frame():
                raise T24TestError(
                    what_happened="Toolbar Authorise not reachable",
                    why="Lost reference to the toolbar between screenshot and click.",
                    how_to_fix="Verify the record view is still open.",
                )

        try:
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(self.TOOLBAR_AUTHORISE)
            )
        except TimeoutException:
            raise T24TestError(
                what_happened="Toolbar Authorise found but never clickable",
                why="The element is in the DOM but not interactable within 10s.",
                how_to_fix="Check for an overlay or modal blocking the toolbar.",
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button
        )
        time.sleep(0.3)

        try:
            button.click()
            logger.info("✓ Toolbar Authorise clicked (native click)")
        except Exception as native_err:
            from selenium.webdriver import ActionChains
            logger.warning(
                f"Native click failed ({type(native_err).__name__}) "
                "— trying ActionChains"
            )
            ActionChains(self.driver).move_to_element(button).click().perform()
            logger.info("✓ Toolbar Authorise clicked (ActionChains)")
    # ================================================================
    # FILL ACTIONS
    # ================================================================

    def fill_main_tab(self, data: dict) -> "CurrentAccountPage":
        """Fill the main tab with customer, mnemonic, account title, short name.
        Category (1001) and Currency (USD) are pre-filled by T24."""
        self.find_visible(self.CUSTOMER)

        # Customer ID — links the account to the customer we created earlier
        self.type(self.CUSTOMER, data["customer_no"])
        time.sleep(0.5)  # let T24's check-file validator fire and enrich

        # Mnemonic — short user-friendly alias
        self.type(self.MNEMONIC, data["mnemonic"])

        # GB Account Name 1 — derived from customer's full name
        self.type(self.ACCOUNT_TITLE_1, data["account_title"])

        # GB Short Name — 3-letter abbreviation
        self.type(self.SHORT_TITLE, data["short_title"])

        logger.info(
            f"Main tab filled — customer: {data['customer_no']}, "
            f"mnemonic: {data['mnemonic']}, "
            f"title: '{data['account_title']}', "
            f"short: '{data['short_title']}'"
        )
        return self

    # ================================================================
    # TOOLBAR ACTIONS
    # ================================================================

    def validate(self) -> "CurrentAccountPage":
        """Click Validate — doToolbar('', 'VAL', '', '')."""
        self.js_click(self.VALIDATE_BUTTON)
        logger.info("Validate triggered")
        return self

    def commit(self) -> "CurrentAccountPage":
        """Click Commit — doToolbar('', 'I', '', '')."""
        self.js_click(self.COMMIT_BUTTON)
        logger.info("Commit triggered")
        return self

    # ================================================================
    # FRAME / TOOLBAR DISCOVERY (re-used pattern from customer page)
    # ================================================================

    def _is_toolbar_present(self) -> bool:
        try:
            return len(self.driver.find_elements(*self.TOOLBAR_AUTHORISE)) > 0
        except Exception:
            return False

    def _find_toolbar_frame(self) -> bool:
        self.driver.switch_to.default_content()
        if self._is_toolbar_present():
            return True

        frames = (
                self.driver.find_elements(By.TAG_NAME, "frame")
                + self.driver.find_elements(By.TAG_NAME, "iframe")
        )
        for frame in frames:
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(frame)
                if self._is_toolbar_present():
                    return True
            except Exception:
                continue

        self.driver.switch_to.default_content()
        return False

    # ================================================================
    # TRANSACTION RESULT
    # ================================================================

    def wait_for_transaction_result(self, timeout: int = 10) -> None:
        """Brief pause for T24 to process and land on the result screen."""
        time.sleep(2)

    def _has_transaction_result(self) -> bool:
        try:
            msgs = self.driver.find_elements(*self.TXN_MESSAGE)
            for m in msgs:
                text = (m.text or "").strip()
                if text.startswith("Txn Complete:") or "Error" in text:
                    return True
            if self.driver.find_elements(*self.ERROR_PAGE_CAPTION):
                return True
        except Exception:
            pass
        return False

    def _find_result_frame(self) -> bool:
        self.driver.switch_to.default_content()
        if self._has_transaction_result():
            return True

        frames = (
                self.driver.find_elements(By.TAG_NAME, "frame")
                + self.driver.find_elements(By.TAG_NAME, "iframe")
        )
        for frame in frames:
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(frame)
                if self._has_transaction_result():
                    return True
            except Exception:
                continue
        self.driver.switch_to.default_content()
        return False

    def get_transaction_result(self) -> dict:
        """Parse the post-commit screen across frames."""
        if not self._find_result_frame():
            return {
                "status": "unknown",
                "message": "(no result indicator found on any frame)",
                "transaction_id": "",
            }

        is_error_page = bool(self.driver.find_elements(*self.ERROR_PAGE_CAPTION))

        try:
            message_text = self.driver.find_element(*self.TXN_MESSAGE).text.strip()
        except Exception:
            message_text = ""

        if is_error_page:
            if not message_text:
                try:
                    message_text = self.driver.find_element(
                        *self.ERROR_HIDDEN_INPUT
                    ).get_attribute("value") or ""
                except Exception:
                    pass
            return {
                "status": "error",
                "message": message_text,
                "transaction_id": "",
            }

        if message_text.startswith("Txn Complete:"):
            parts = message_text.split()
            return {
                "status": "success",
                "message": message_text,
                "transaction_id": parts[2] if len(parts) > 2 else "",
            }

        return {
            "status": "unknown",
            "message": message_text or "(no message found)",
            "transaction_id": "",
        }
