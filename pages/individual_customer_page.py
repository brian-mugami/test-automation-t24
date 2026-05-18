"""T24 Individual Customer page (CUSTOMER application).

Covers both flows on the same record:
- INPUT  (INPUTTER): fill three tabs → validate → commit
- AUTH   (AUTHORISER): wait for record after drilldown → authorise
"""
import logging
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


class IndividualCustomerPage(BasePage):

    # ================================================================
    # LOCATORS
    # ================================================================

    # ---------- Header ----------
    TRANSACTION_ID = (By.CSS_SELECTOR, "span.iddisplay")

    # ---------- Tabs (changed via T24's changetab(tabN) JS) ----------
    TAB_IDS = {
        "Customer": "tab1",
        "Physical Address": "tab2",
        "Contact Details": "tab3",
        "ID Doc": "tab4",
        "Relation": "tab5",
        "Further Details": "tab6",
        "Financial Details": "tab7",
        "Residential Details": "tab8",
        "Communication Details": "tab9",
        "KYC": "tab10",
        "Other Details": "tab11",
        "Reporting Details": "tab12",
        "Exit Status": "tab13",
        "Audit": "tab14",
    }

    # ---------- Customer tab fields ----------
    TITLE = (By.ID, "fieldName:TITLE")
    GIVEN_NAMES = (By.ID, "fieldName:GIVEN.NAMES")
    FAMILY_NAME = (By.ID, "fieldName:FAMILY.NAME")
    GB_FULL_NAME = (By.ID, "fieldName:NAME.1:1")
    GB_SHORT_NAME = (By.ID, "fieldName:SHORT.NAME:1")
    MNEMONIC = (By.ID, "fieldName:MNEMONIC")
    GENDER_MALE = (By.XPATH,
                   "//input[@name='radio:tab1:GENDER' and @value='MALE']")
    GENDER_FEMALE = (By.XPATH,
                     "//input[@name='radio:tab1:GENDER' and @value='FEMALE']")
    SECTOR = (By.ID, "fieldName:SECTOR")
    NATIONALITY = (By.ID, "fieldName:NATIONALITY")
    CUST_BIRTH_COUNTRY = (By.ID, "fieldName:CUST.BIRTH.COUNTRY")
    CUST_BIRTH_CITY = (By.ID, "fieldName:CUST.BIRTH.CITY")
    DATE_OF_BIRTH = (By.ID, "fieldName:DATE.OF.BIRTH")

    # ---------- Physical Address tab fields ----------
    ADDRESS_COUNTRY = (By.ID, "fieldName:ADDRESS.COUNTRY")
    ADDRESS_TYPE = (By.ID, "fieldName:ADDRESS.TYPE")
    ADDRESS_PURPOSE = (By.ID, "fieldName:ADDRESS.PURPOSE")
    BUILDING_NUMBER = (By.ID, "fieldName:BUILDING.NUMBER")
    STREET = (By.ID, "fieldName:STREET:1")
    TOWN_CITY = (By.ID, "fieldName:TOWN.COUNTRY:1")
    POST_CODE = (By.ID, "fieldName:POST.CODE:1")
    DISTRICT_NAME = (By.ID, "fieldName:DISTRICT.NAME")
    GB_COUNTRY = (By.ID, "fieldName:COUNTRY:1")

    # ---------- Contact Details tab fields ----------
    PHONE_HOME = (By.ID, "fieldName:PHONE.1:1")
    PHONE_MOBILE = (By.ID, "fieldName:SMS.1:1")
    EMAIL = (By.ID, "fieldName:EMAIL.1:1")
    IDD_PREFIX_PHONE = (By.ID, "fieldName:IDD.PREFIX.PHONE:1")
    SECURE_MESSAGE = (By.ID, "CheckBox:fieldName:SECURE.MESSAGE")

    # ---------- Toolbar buttons ----------
    VALIDATE_BUTTON = (By.XPATH, "//a[@accesskey='V']")
    COMMIT_BUTTON = (By.XPATH, "//a[@accesskey='C']")

    # Toolbar Authorise — appears on an open record (post-drilldown).
    # Distinct from the queue's drilldown link (title='Authorise' only).
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

    # ================================================================
    # GENERIC HELPERS
    # ================================================================

    def read_transaction_id(self) -> str:
        """Read the system-generated transaction ID from the form header."""
        return self.find_visible(self.TRANSACTION_ID).text.strip()

    def select_dropdown(self, locator: tuple, value: str) -> None:
        """Pick an option from a <select> by its value attribute."""
        element = self.find_visible(locator)
        Select(element).select_by_value(value)

    def switch_to_tab(self, tab_name: str) -> "IndividualCustomerPage":
        """Switch tab via T24's internal changetab() function — faster
        than clicking and immune to anchor-click interception."""
        tab_id = self.TAB_IDS.get(tab_name)
        if not tab_id:
            raise ValueError(
                f"Unknown tab '{tab_name}'. "
                f"Known tabs: {sorted(self.TAB_IDS)}"
            )
        self.driver.execute_script(f"changetab('{tab_id}');")
        logger.info(f"Switched to tab: {tab_name} ({tab_id})")
        return self

    def build_mnemonic(self, customer_data: dict) -> str:
        """Read the transaction ID from the form and build the mnemonic.
        Format: M<transaction_id>. Stored back into customer_data."""
        tx_id = self.read_transaction_id()
        mnemonic = f"M{tx_id}"
        customer_data["mnemonic"] = mnemonic
        return mnemonic

    # ================================================================
    # FRAME / TOOLBAR DISCOVERY (for the AUTHORISER flow)
    # ================================================================

    def _is_toolbar_present(self) -> bool:
        """Whether the toolbar Authorise button exists in the current frame."""
        try:
            return len(self.driver.find_elements(*self.TOOLBAR_AUTHORISE)) > 0
        except Exception:
            return False

    def _find_toolbar_frame(self) -> bool:
        """Walk every frame/iframe looking for the toolbar Authorise button.
        On success, leaves the driver scoped to the frame that contains it
        so subsequent operations work without re-searching."""
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
    # INPUT FLOW — fill tabs, validate, commit
    # ================================================================

    def fill_customer_tab(self, data: dict) -> "IndividualCustomerPage":
        """Fill all required and key fields on the Customer tab."""
        self.switch_to_tab("Customer")
        self.find_visible(self.TITLE)  # wait for tab content to render

        self.select_dropdown(self.TITLE, data["title"])

        self.type(self.GIVEN_NAMES, data["given_name"])
        self.type(self.FAMILY_NAME, data["family_name"])
        self.type(self.GB_FULL_NAME, data["gb_full_name"])
        self.type(self.GB_SHORT_NAME, data["gb_short_name"])

        self.type(self.MNEMONIC, data["mnemonic"])

        if data["gender"] == "MALE":
            self.js_click(self.GENDER_MALE)
        else:
            self.js_click(self.GENDER_FEMALE)

        self.type(self.SECTOR, data["sector"])
        self.type(self.NATIONALITY, data["nationality"])
        self.type(self.CUST_BIRTH_COUNTRY, data["cust_birth_country"])
        self.type(self.CUST_BIRTH_CITY, data["cust_birth_city"])

        if data.get("date_of_birth"):
            self.type(self.DATE_OF_BIRTH, data["date_of_birth"])

        return self

    def fill_physical_address_tab(self, data: dict) -> "IndividualCustomerPage":
        """Fill all fields on the Physical Address tab."""
        self.switch_to_tab("Physical Address")

        # Two country fields — set both explicitly
        self.type(self.ADDRESS_COUNTRY, data["address_country"])
        self.type(self.GB_COUNTRY, data["country"])

        self.select_dropdown(self.ADDRESS_TYPE, data["address_type"])
        self.select_dropdown(self.ADDRESS_PURPOSE, data["address_purpose"])

        self.type(self.BUILDING_NUMBER, data["building_number"])
        self.type(self.STREET, data["street"])
        self.type(self.TOWN_CITY, data["town_city"])
        self.type(self.POST_CODE, data["post_code"])
        self.type(self.DISTRICT_NAME, data["district_name"])

        return self

    def fill_contact_details_tab(self, data: dict) -> "IndividualCustomerPage":
        """Fill all fields on the Contact Details tab."""
        self.switch_to_tab("Contact Details")

        self.type(self.PHONE_HOME, data["phone_home"])
        self.type(self.PHONE_MOBILE, data["phone_mobile"])
        self.type(self.EMAIL, data["email"])
        # Secure Message left unchecked by requirement

        return self

    def validate(self) -> "IndividualCustomerPage":
        """Click Validate — T24 calls doToolbar('', 'VAL', '', '')."""
        self.js_click(self.VALIDATE_BUTTON)
        logger.info("Validate triggered")
        return self

    def commit(self) -> "IndividualCustomerPage":
        """Click Commit — T24 calls doToolbar('', 'I', '', '')."""
        self.js_click(self.COMMIT_BUTTON)
        logger.info("Commit triggered")
        return self

    # ================================================================
    # AUTHORISER FLOW — record loaded after drilldown
    # ================================================================

    def wait_for_record_loaded(self, timeout: int = 30) -> None:
        """Wait for the record view to render after a drilldown click.

        Gives T24 a moment to render the lower div, then walks every
        frame looking for the toolbar Authorise button. Leaves the
        driver scoped to the frame containing the toolbar.
        """
        time.sleep(2)  # let T24 begin rendering the lower div

        end = time.time() + timeout
        while time.time() < end:
            if self._find_toolbar_frame():
                logger.info("✓ Record loaded — toolbar Authorise reachable")
                return
            time.sleep(1)

        # Failed — save a screenshot so we can see what T24 rendered
        self.driver.switch_to.default_content()
        self.screenshot("DEBUG_record_not_loaded")
        raise T24TestError(
            what_happened="Customer record did not load after drilldown",
            why=(
                f"Searched every frame for "
                f"<a accesskey='A' title='Authorises a deal'> for {timeout}s "
                "but never found it. The drilldown may not have navigated, "
                "or the toolbar lives in unexpected DOM. Saved "
                "DEBUG_record_not_loaded.png for inspection."
            ),
            how_to_fix=(
                "Open the DEBUG screenshot. If the record IS visible, the "
                "toolbar is in an unexpected DOM location. If the record "
                "is NOT visible, the drilldown click did not fire."
            ),
        )

    def scroll_to_toolbar_authorise(self) -> None:
        """Bring the toolbar Authorise button into view for the screenshot.
        Assumes wait_for_record_loaded has placed us in the right frame;
        re-acquires it if the frame context was lost."""
        if not self._is_toolbar_present():
            self._find_toolbar_frame()

        try:
            btn = self.driver.find_element(*self.TOOLBAR_AUTHORISE)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", btn
            )
            time.sleep(0.5)  # let scroll settle before screenshot
            logger.info("Scrolled toolbar Authorise into view for screenshot")
        except NoSuchElementException:
            logger.warning("Toolbar Authorise button not found for scroll")

    def authorise(self) -> None:
        """Click the toolbar Authorise button to commit the authorisation.

        Uses a native Selenium click (rather than execute_script) for the
        same reason the drilldown needed it — synthetic clicks don't always
        invoke T24's javascript: links reliably.
        """
        if not self._is_toolbar_present():
            if not self._find_toolbar_frame():
                raise T24TestError(
                    what_happened="Toolbar Authorise not reachable for click",
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

        # Scroll into view and use native click
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button
        )
        time.sleep(0.3)

        try:
            button.click()
            logger.info("✓ Toolbar Authorise clicked (native Selenium click)")
        except Exception as native_err:
            from selenium.webdriver import ActionChains
            logger.warning(
                f"Native click failed ({type(native_err).__name__}) "
                f"— trying ActionChains"
            )
            ActionChains(self.driver).move_to_element(button).click().perform()
            logger.info("✓ Toolbar Authorise clicked (ActionChains)")

    # ================================================================
    # TRANSACTION RESULT (success / error detection)
    # ================================================================

    def _has_transaction_result(self) -> bool:
        """Whether the current frame shows a Txn Complete or error indicator."""
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
        """Walk every frame looking for a transaction result indicator.
        Leaves the driver in the frame that has it."""
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
                    logger.info(
                        f"Result message found in frame "
                        f"id='{frame.get_attribute('id') or '?'}'"
                    )
                    return True
            except Exception:
                continue

        self.driver.switch_to.default_content()
        return False

    def wait_for_transaction_result(self, timeout: int = 15) -> None:
        """Poll across all frames for a Txn Complete or error indicator."""
        end = time.time() + timeout
        while time.time() < end:
            if self._find_result_frame():
                logger.info("✓ Transaction result located")
                return
            time.sleep(1)

        # No clear result — capture state and let the parser handle it
        self.driver.switch_to.default_content()
        self.screenshot("DEBUG_no_transaction_result")
        logger.warning(
            f"No transaction result indicator found within {timeout}s — "
            "saved DEBUG_no_transaction_result.png"
        )

    def get_transaction_result(self) -> dict:
        """Parse the post-action result. Searches across frames since T24
        may render the message in a different frame than where we acted.

        Returns:
            dict with 'status' ('success'|'error'|'unknown'),
            'message' (T24 text), 'transaction_id' (str).
        """
        # Move into whichever frame has the result indicator
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

        # Success format:
        # "Txn Complete: <id> <hh:mm:ss> <dd> <MMM> <yyyy> <APP>,<VERSION> <FN>"
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