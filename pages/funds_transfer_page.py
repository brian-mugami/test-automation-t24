"""T24 Funds Transfer page (FUNDS.TRANSFER,ACTR.FTHP version).

Covers both flows:
- INPUT  (INPUTTER):   fill form → validate → commit
- AUTH   (AUTHORISER): wait for record after drilldown → authorise
"""
import logging
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


class FundsTransferPage(BasePage):

    # ---------- Header ----------
    TRANSACTION_ID_HIDDEN = (By.ID, "transactionId")
    TRANSACTION_ID_DISPLAY = (By.CSS_SELECTOR, "span.iddisplay")

    # ---------- Tabs ----------
    TAB_IDS = {
        "Transfer Between Accounts": "tab1",
        "Audit": "tab2",
    }

    # ---------- Tab 1 fields ----------
    DEBIT_ACCT_NO     = (By.ID, "fieldName:DEBIT.ACCT.NO")
    DEBIT_CURRENCY    = (By.ID, "fieldName:DEBIT.CURRENCY")
    DEBIT_AMOUNT      = (By.ID, "fieldName:DEBIT.AMOUNT")
    DEBIT_VALUE_DATE  = (By.ID, "fieldName:DEBIT.VALUE.DATE")
    DEBIT_THEIR_REF   = (By.ID, "fieldName:DEBIT.THEIR.REF")
    ORDERING_CUST     = (By.ID, "fieldName:ORDERING.CUST:1")
    CREDIT_ACCT_NO    = (By.ID, "fieldName:CREDIT.ACCT.NO")
    CREDIT_CURRENCY   = (By.ID, "fieldName:CREDIT.CURRENCY")
    CREDIT_AMOUNT     = (By.ID, "fieldName:CREDIT.AMOUNT")
    CREDIT_VALUE_DATE = (By.ID, "fieldName:CREDIT.VALUE.DATE")
    CREDIT_THEIR_REF  = (By.ID, "fieldName:CREDIT.THEIR.REF")
    ACCEPT_OVERRIDES = (By.ID, "errorImg")
    # ---------- Toolbar ----------
    VALIDATE_BUTTON = (By.XPATH, "//a[@accesskey='V']")
    COMMIT_BUTTON   = (By.XPATH, "//a[@accesskey='C']")
    TOOLBAR_AUTHORISE = (
        By.XPATH,
        "//a[@accesskey='A' and @title='Authorises a deal']"
    )

    # ---------- Result detection ----------
    TXN_MESSAGE         = (By.CSS_SELECTOR, "td.message")
    ERROR_PAGE_CAPTION  = (By.XPATH,
        "//td[@class='caption' and contains(text(), 'Error Message')]")
    ERROR_HIDDEN_INPUT  = (By.ID, "errorMessageFromT24")

    # ================================================================
    # HEADER / ID
    # ================================================================
    def read_transaction_id(self) -> str:
        if not self._is_form_present():
            self._find_form_frame()
        # ... rest unchanged
        try:
            hidden = self.driver.find_element(*self.TRANSACTION_ID_HIDDEN)
            val = (hidden.get_attribute("value") or "").strip()
            if val:
                return val
        except NoSuchElementException:
            pass
        return self.find_visible(self.TRANSACTION_ID_DISPLAY).text.strip().replace("/", "")

    def switch_to_tab(self, tab_name: str) -> "FundsTransferPage":
        tab_id = self.TAB_IDS.get(tab_name)
        if not tab_id:
            raise ValueError(
                f"Unknown tab '{tab_name}'. Known: {sorted(self.TAB_IDS)}"
            )
        self.driver.execute_script(f"changetab('{tab_id}');")
        logger.info(f"Switched to tab: {tab_name} ({tab_id})")
        return self

    # ================================================================
    # FRAME / TOOLBAR DISCOVERY (AUTHORISER flow)
    # ================================================================
    def _is_form_present(self) -> bool:
        """Check if the FT form's debit-account field is in current frame."""
        try:
            return len(self.driver.find_elements(*self.DEBIT_ACCT_NO)) > 0
        except Exception:
            return False

    def _find_form_frame(self) -> bool:
        """Walk every frame/iframe looking for the FT form."""
        self.driver.switch_to.default_content()
        if self._is_form_present():
            return True

        frames = (
                self.driver.find_elements(By.TAG_NAME, "frame")
                + self.driver.find_elements(By.TAG_NAME, "iframe")
        )
        for frame in frames:
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(frame)
                if self._is_form_present():
                    fid = frame.get_attribute("id") or "?"
                    logger.info(f"FT form found in frame id='{fid}'")
                    return True
            except Exception:
                continue

        self.driver.switch_to.default_content()
        return False

    def wait_for_form_loaded(self, timeout: int = 20) -> None:
        """Wait for the FT form to render in any frame."""
        import time
        time.sleep(1)
        end = time.time() + timeout
        while time.time() < end:
            if self._find_form_frame():
                logger.info("✓ FT form loaded — fields reachable")
                return
            time.sleep(1)

        self.driver.switch_to.default_content()
        self.screenshot("DEBUG_ft_form_not_loaded")
        raise T24TestError(
            what_happened="FT form did not load after drilldown",
            why=(
                f"Walked every frame for {timeout}s but never found the "
                "DEBIT.ACCT.NO field. Saved DEBUG_ft_form_not_loaded.png."
            ),
            how_to_fix="Open the DEBUG screenshot to verify visual state.",
        )
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
                    logger.info(
                        f"Toolbar found in frame "
                        f"id='{frame.get_attribute('id') or '?'}'"
                    )
                    return True
            except Exception:
                continue

        self.driver.switch_to.default_content()
        return False

    # ================================================================
    # INPUT FLOW
    # ================================================================

    def fill_transfer_form(self, data: dict) -> "FundsTransferPage":
        if not self._is_form_present():
            self._find_form_frame()

        self.switch_to_tab("Transfer Between Accounts")
        self.find_visible(self.DEBIT_ACCT_NO)  # wait for tab render

        self.type(self.DEBIT_ACCT_NO, data["debit_account"])
        self.type(self.DEBIT_CURRENCY, "USD")
        self.type(self.DEBIT_AMOUNT, str(data["debit_amount"]))

        if data.get("debit_value_date"):
            self.type(self.DEBIT_VALUE_DATE, data["debit_value_date"])

        self.type(self.CREDIT_ACCT_NO, data["credit_account"])
        self.type(self.CREDIT_CURRENCY, "USD")

        if data.get("credit_value_date"):
            self.type(self.CREDIT_VALUE_DATE, data["credit_value_date"])

        return self

    def validate(self) -> "FundsTransferPage":
        self.js_click(self.VALIDATE_BUTTON)
        logger.info("Validate triggered")
        return self

    def commit(self) -> "FundsTransferPage":
        self.js_click(self.COMMIT_BUTTON)
        logger.info("Commit triggered")
        return self

    # ================================================================
    # AUTHORISER FLOW
    # ================================================================

    def wait_for_record_loaded(self, timeout: int = 30) -> None:
        time.sleep(2)
        end = time.time() + timeout
        while time.time() < end:
            if self._find_toolbar_frame():
                logger.info("✓ FT record loaded — toolbar Authorise reachable")
                return
            time.sleep(1)

        self.driver.switch_to.default_content()
        self.screenshot("DEBUG_ft_record_not_loaded")
        raise T24TestError(
            what_happened="FT record did not load after drilldown",
            why=(
                f"Searched every frame for toolbar Authorise for {timeout}s "
                "but never found it. Saved DEBUG_ft_record_not_loaded.png."
            ),
            how_to_fix="Open the DEBUG screenshot to verify visual state.",
        )

    def scroll_to_toolbar_authorise(self) -> None:
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
        if not self._is_toolbar_present():
            if not self._find_toolbar_frame():
                raise T24TestError(
                    what_happened="Toolbar Authorise not reachable",
                    why="Lost toolbar frame reference.",
                    how_to_fix="Verify the FT record is still open.",
                )

        try:
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(self.TOOLBAR_AUTHORISE)
            )
        except TimeoutException:
            raise T24TestError(
                what_happened="Toolbar Authorise found but never clickable",
                why="In DOM but not interactable within 10s.",
                how_to_fix="Check for an overlay blocking the toolbar.",
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button
        )
        time.sleep(0.3)
        try:
            button.click()
            logger.info("✓ Toolbar Authorise clicked (native)")
        except Exception as e:
            logger.warning(
                f"Native click failed ({type(e).__name__}) — ActionChains"
            )
            ActionChains(self.driver).move_to_element(button).click().perform()
            logger.info("✓ Toolbar Authorise clicked (ActionChains)")

    # ================================================================
    # TRANSACTION RESULT
    # ================================================================
    def has_overrides_popup(self, wait_seconds: float = 2.0) -> bool:
        if not self._is_form_present():
            self._find_form_frame()

        end = time.time() + wait_seconds
        while time.time() < end:
            try:
                elements = self.driver.find_elements(*self.ACCEPT_OVERRIDES)
                if any(e.is_displayed() for e in elements):
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def accept_overrides(self) -> "FundsTransferPage":
        """Click the 'Accept Overrides' link to confirm and proceed."""
        if not self._is_form_present():
            self._find_form_frame()

        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(self.ACCEPT_OVERRIDES)
            )
        except TimeoutException:
            raise T24TestError(
                what_happened="Accept Overrides link not clickable",
                why="Element in DOM but not interactable within 10s.",
                how_to_fix="Check for an overlay blocking the override prompt.",
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", btn
        )
        time.sleep(0.3)

        try:
            btn.click()
            logger.info("✓ Accept Overrides clicked (native)")
        except Exception as e:
            logger.warning(
                f"Native click failed ({type(e).__name__}) — execute_script"
            )
            self.driver.execute_script("arguments[0].click();", btn)
            logger.info("✓ Accept Overrides clicked (execute_script)")

        time.sleep(2)
        return self

    def wait_for_transaction_result(self, timeout: int = 10) -> None:
        time.sleep(2)

    def get_transaction_result(self) -> dict:
        try:
            self.switch_to_default()
        except Exception:
            self.driver.switch_to.default_content()

        is_error_page = self.is_present(self.ERROR_PAGE_CAPTION, timeout=2)

        try:
            message_text = self.find(self.TXN_MESSAGE).text.strip()
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
            return {"status": "error", "message": message_text, "transaction_id": ""}

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