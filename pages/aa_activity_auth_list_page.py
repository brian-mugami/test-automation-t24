"""T24 AA.ARRANGEMENT.ACTIVITY-NAU enquiry search and results."""
import logging
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from pages.base_page import BasePage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


class AAActivityAuthListPage(BasePage):
    """Page object for Unauthorized AAA records.

    This enquiry first shows a selection screen. After entering the customer
    number and clicking Find, it renders AA activity rows with View, Authorise,
    and Delete drilldowns.
    """

    MAX_FRAME_DEPTH = 5

    ARRANGEMENT_SELECTOR = (By.ID, "value:1:1:1")
    ARRANGEMENT_OPERAND = (By.NAME, "operand:1:1:1")
    CUSTOMER_SELECTOR = (By.ID, "value:2:1:1")
    CUSTOMER_OPERAND = (By.NAME, "operand:2:1:1")
    ACTIVITY_SELECTOR = (By.ID, "value:3:1:1")
    ACTIVITY_OPERAND = (By.NAME, "operand:3:1:1")
    ACTIVITY_DESCRIPTION = "New Activity for Arrangement"
    FIND_BUTTON = (
        By.XPATH,
        "//a[@title='Run Selection' or normalize-space(.)='Find']"
    )
    RESULTS_TABLE = (
        By.CSS_SELECTOR,
        "table.enquirydata_AAARRANGEMENTACTIVITYNAU, "
        "table[id^='datadisplay_']"
    )
    PENDING_ROWS = (
        By.XPATH,
        "//table[contains(@class, 'enquirydata_AAARRANGEMENTACTIVITYNAU') "
        "or starts-with(@id, 'datadisplay_')]"
        "//tr[.//a[@title='Authorise']]"
    )
    APPROVAL_DRILLBOX = (
        By.XPATH,
        "//select[starts-with(@id, 'drillbox:') and "
        ".//option[@value='Approve' or normalize-space(.)='Approve']]"
    )
    SELECT_DRILLDOWN = (
        By.XPATH,
        "//a[@title='Select Drilldown' or .//img[@alt='Select Drilldown']]"
    )
    TOOLBAR_AUTHORISE = (
        By.XPATH,
        "//a[@accesskey='A' and @title='Authorises a deal']"
    )
    TXN_MESSAGE = (By.CSS_SELECTOR, "td.message, .message, #message")

    @staticmethod
    def _selection_value_for(field_name):
        return (
            By.XPATH,
            "//table[starts-with(@id, 'selectiondisplay_') "
            "or contains(@class, 'enqsel-vert')]"
            "//tr[.//input[starts-with(@name, 'fieldName:') "
            f"and @value='{field_name}']]"
            "//input[@type='text' and starts-with(@name, 'value:')]"
        )

    @staticmethod
    def _selection_operand_for(field_name):
        return (
            By.XPATH,
            "//table[starts-with(@id, 'selectiondisplay_') "
            "or contains(@class, 'enqsel-vert')]"
            "//tr[.//input[starts-with(@name, 'fieldName:') "
            f"and @value='{field_name}']]"
            "//select[starts-with(@name, 'operand:')]"
        )

    @staticmethod
    def _selection_values_except(field_name):
        return (
            By.XPATH,
            "//table[starts-with(@id, 'selectiondisplay_') "
            "or contains(@class, 'enqsel-vert')]"
            "//tr[.//input[starts-with(@name, 'fieldName:') "
            f"and @value!='{field_name}']]"
            "//input[@type='text' and starts-with(@name, 'value:')]"
        )

    def _search_frames(self, locator, depth):
        try:
            if self.driver.find_elements(*locator):
                return True
        except Exception:
            pass
        if depth >= self.MAX_FRAME_DEPTH:
            return False
        count = (len(self.driver.find_elements(By.TAG_NAME, "frame"))
                 + len(self.driver.find_elements(By.TAG_NAME, "iframe")))
        for i in range(count):
            try:
                frames = (self.driver.find_elements(By.TAG_NAME, "frame")
                          + self.driver.find_elements(By.TAG_NAME, "iframe"))
                if i >= len(frames):
                    break
                self.driver.switch_to.frame(frames[i])
                if self._search_frames(locator, depth + 1):
                    return True
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    self.driver.switch_to.default_content()
        return False

    def _switch_to_frame_with(self, locator, what, timeout=25):
        end = time.time() + timeout
        while time.time() < end:
            self.driver.switch_to.default_content()
            if self._search_frames(locator, depth=0):
                return True
            time.sleep(0.5)
        self.screenshot(f"DEBUG_aa_auth_{what}_not_found")
        return False

    def wait_for_search_loaded(self, timeout=30):
        if not self._switch_to_frame_with(
                self._selection_value_for("ARRANGEMENT"), "search", timeout):
            raise T24TestError(
                what_happened="AA auth search screen did not load",
                why=("Walked every frame but did not find the arrangement "
                     "selection row whose fieldName is ARRANGEMENT."),
                how_to_fix="Open DEBUG_aa_auth_search_not_found.png.",
            )
        logger.info("Unauthorized AAA records search screen loaded")
        return self

    def search_by_customer(self, customer_no, timeout=30):
        self.wait_for_search_loaded(timeout=timeout)
        self._set_operand(self.CUSTOMER_OPERAND, value="EQ")
        field = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(self.CUSTOMER_SELECTOR)
        )
        field.clear()
        field.send_keys(str(customer_no))

        find = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(self.FIND_BUTTON)
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", find)
        time.sleep(0.3)
        try:
            find.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", find)
        logger.info(f"Ran Unauthorized AAA search for customer {customer_no}")
        return self.wait_for_results_loaded(timeout=timeout)

    def search_by_arrangement(self, arrangement_id, timeout=30):
        self.wait_for_search_loaded(timeout=timeout)

        self._set_operand(self._selection_operand_for("ARRANGEMENT"), value="CT")
        self._clear_selection_values_except("ARRANGEMENT")

        field = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(
                self._selection_value_for("ARRANGEMENT"))
        )
        self._set_field(field, arrangement_id)
        logger.info(
            "AA auth search criteria before Find: "
            f"Arrangement={self._field_value(self._selection_value_for('ARRANGEMENT'))!r}, "
            f"Customer={self._field_value(self._selection_value_for('CUSTOMER'))!r}, "
            f"Activity={self._field_value(self._selection_value_for('@ID'))!r}"
        )

        find = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(self.FIND_BUTTON)
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", find)
        time.sleep(0.3)
        try:
            find.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", find)
        logger.info(
            f"Ran Unauthorized AAA search for arrangement {arrangement_id}")
        return self.wait_for_results_loaded(timeout=timeout)

    def _clear_field(self, locator):
        try:
            field = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(locator)
            )
            self._set_field(field, "")
        except Exception as e:
            logger.warning(f"Could not clear enquiry field {locator}: {e}")

    def _clear_selection_values_except(self, field_name):
        try:
            fields = self.driver.find_elements(
                *self._selection_values_except(field_name))
            for field in fields:
                self._set_field(field, "")
        except Exception as e:
            logger.warning(
                f"Could not clear non-{field_name} enquiry fields: {e}")

    def _set_field(self, field, value):
        text = str(value)
        self.driver.execute_script(
            """
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
            arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
            arguments[0].blur();
            """,
            field,
            text,
        )
        try:
            field.clear()
            if text:
                field.send_keys(text)
                field.send_keys("\t")
            else:
                field.send_keys("\t")
        except Exception:
            pass
        self.driver.execute_script(
            """
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
            arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
            arguments[0].blur();
            """,
            field,
            text,
        )

    def _field_value(self, locator):
        try:
            return self.driver.find_element(*locator).get_attribute("value")
        except Exception:
            return None

    def _set_operand(self, locator, value):
        try:
            operator = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(locator)
            )
            select = Select(operator)
            values = [o.get_attribute("value") for o in select.options]
            if value in values:
                select.select_by_value(value)
            else:
                logger.warning(
                    f"Operand {locator} has values {values}; leaving as-is")
                return
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                operator)
        except Exception as e:
            logger.warning(f"Could not set enquiry operand {locator}: {e}")

    def wait_for_results_loaded(self, timeout=30):
        if not self._switch_to_frame_with(
                self.PENDING_ROWS, "results", timeout):
            raise T24TestError(
                what_happened="Unauthorized AAA results did not load",
                why="The results table did not contain any Authorise rows.",
                how_to_fix="Open DEBUG_aa_auth_results_not_found.png.",
            )
        logger.info("Unauthorized AAA records results loaded")
        return self

    def list_pending_arrangements(self):
        self.wait_for_results_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)
        pending = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 13:
                continue
            pending.append({
                "customer": cells[0].text.strip(),
                "name": cells[1].text.strip(),
                "arrangement_id": cells[2].text.strip(),
                "product": cells[3].text.strip(),
                "currency": cells[4].text.strip(),
                "activity": cells[7].text.strip(),
                "date": cells[11].text.strip(),
                "status": cells[12].text.strip(),
            })
        return pending

    def _switch_to_new_window_if_opened(self, before_handles):
        new_handles = [
            h for h in self.driver.window_handles
            if h not in before_handles
        ]
        if new_handles:
            self.driver.switch_to.window(new_handles[-1])
            try:
                self.driver.maximize_window()
            except Exception:
                pass
            return True
        return False

    def click_authorise_for_arrangement(
            self, arrangement_id, customer=None,
            activity_description=ACTIVITY_DESCRIPTION):
        self.wait_for_results_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)
        available = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 8:
                continue
            row_customer = cells[0].text.strip()
            row_name = cells[1].text.strip()
            row_arrangement = cells[2].text.strip()
            row_activity = cells[7].text.strip()
            if row_arrangement:
                available.append({
                    "customer": row_customer,
                    "name": row_name,
                    "arrangement_id": row_arrangement,
                    "activity": row_activity,
                })
            if (row_arrangement == arrangement_id
                    and row_activity == activity_description
                    and (customer is None or row_customer == str(customer))
                    and row_name):
                auth_link = row.find_element(By.XPATH, ".//a[@title='Authorise']")
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    auth_link)
                time.sleep(0.5)
                before_handles = set(self.driver.window_handles)
                try:
                    auth_link.click()
                except Exception:
                    ActionChains(self.driver).move_to_element(
                        auth_link).click().perform()
                time.sleep(2)
                self._switch_to_new_window_if_opened(before_handles)
                logger.info(
                    f"Clicked Authorise for AA {arrangement_id} "
                    f"customer {row_customer} {row_name}"
                )
                return

        raise NoSuchElementException(
            f"AA arrangement '{arrangement_id}' was not found in the "
            f"Unauthorized AAA records results with activity "
            f"'{activity_description}'. Available rows: {available}"
        )

    def wait_for_approval_drillbox(self, timeout=30):
        if not self._switch_to_frame_with(
                self.APPROVAL_DRILLBOX, "approval_drillbox", timeout):
            raise T24TestError(
                what_happened="AA approval drillbox did not load",
                why="The Approve/View/Edit/Delete selection was not found.",
                how_to_fix="Open DEBUG_aa_auth_approval_drillbox_not_found.png.",
            )
        logger.info("AA approval drillbox loaded")
        return self

    def select_approve_drilldown(self, timeout=30):
        self.wait_for_approval_drillbox(timeout=timeout)
        drillbox = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(self.APPROVAL_DRILLBOX)
        )
        Select(drillbox).select_by_value("Approve")
        self.driver.execute_script(
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            drillbox)

        go = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(self.SELECT_DRILLDOWN)
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", go)
        time.sleep(0.3)
        before_handles = set(self.driver.window_handles)
        try:
            go.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", go)
        logger.info("Selected Approve drilldown for AA activity")
        time.sleep(2)
        self._switch_to_new_window_if_opened(before_handles)
        return self

    def wait_for_authorise_toolbar(self, timeout=30):
        if not self._switch_to_frame_with(
                self.TOOLBAR_AUTHORISE, "authorise_toolbar", timeout):
            raise T24TestError(
                what_happened="AA final authorise screen did not load",
                why="The toolbar Authorise button was not found.",
                how_to_fix="Open DEBUG_aa_auth_authorise_toolbar_not_found.png.",
            )
        logger.info("AA final authorise toolbar loaded")
        return self

    def authorise_activity(self, timeout=30):
        self.wait_for_authorise_toolbar(timeout=timeout)
        button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(self.TOOLBAR_AUTHORISE)
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(0.3)
        try:
            button.click()
        except Exception:
            ActionChains(self.driver).move_to_element(button).click().perform()
        logger.info("Clicked final AA Authorise toolbar button")
        time.sleep(3)
        return self

    def get_transaction_result(self):
        self._switch_to_frame_with(self.TXN_MESSAGE, "authorise_result", timeout=15)
        try:
            message = self.driver.find_element(*self.TXN_MESSAGE).text.strip()
        except Exception:
            message = ""

        if message.startswith("Txn Complete:"):
            return {"status": "success", "message": message}
        if message:
            return {"status": "unknown", "message": message}
        return {"status": "unknown", "message": "(no message found)"}
