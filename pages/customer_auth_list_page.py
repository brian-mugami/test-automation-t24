"""T24 CUSTOMER.NAU enquiry — list of customer records pending authorisation."""
import logging

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from pages.base_page import BasePage
import time
from selenium.webdriver import ActionChains

logger = logging.getLogger(__name__)


class CustomerAuthListPage(BasePage):
    """Page object for the enquiry list showing customers held for authorisation.

    The list is a standard T24 enquiry: each pending record is a row, and the
    first column holds the customer ID. To act on a specific record we read
    that column, compare to the stored ID, and click that row's Authorise
    drilldown — explicit verification rather than a wildcard match.
    """

    # Rows in the enquiry that have an Authorise drilldown — these are the
    # pending-customer rows we care about.
    PENDING_ROWS = (By.XPATH, "//tr[.//a[@title='Authorise']]")

    def _wait_for_list_loaded(self, timeout: int = 15) -> None:
        """Wait for at least one pending row to be present."""
        try:
            self.wait.until(
                lambda d: len(d.find_elements(*self.PENDING_ROWS)) > 0
            )
        except TimeoutException:
            raise TimeoutException(
                "The customer authorisation queue did not load any rows "
                f"within {timeout}s."
            )

    def list_pending_ids(self) -> list[str]:
        """Return all customer IDs currently in the queue (first column of each row)."""
        self._wait_for_list_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)
        return [
            row.find_element(By.XPATH, "./td[1]").text.strip()
            for row in rows
        ]

    def is_record_listed(self, customer_id: str) -> bool:
        """Check whether a customer appears in the queue."""
        try:
            return customer_id in self.list_pending_ids()
        except TimeoutException:
            return False


    def click_authorise_for(self, customer_no: str) -> None:
        self._wait_for_list_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)

        logger.info(
            f"Searching {len(rows)} pending records for customer ID '{customer_no}'"
        )

        for row in rows:
            first_cell_text = row.find_element(By.XPATH, "./td[1]").text.strip()
            if first_cell_text == customer_no:
                logger.info(f"  ✓ Match: {first_cell_text}")

                auth_link = row.find_element(By.XPATH, ".//a[@title='Authorise']")

                # Scroll into view so the click lands cleanly
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", auth_link
                )
                time.sleep(0.5)

                # Native Selenium click — dispatches a real mouse event so
                # T24's drilldown() can read the enquiry context from it.
                try:
                    auth_link.click()
                    logger.info("  Drilldown clicked (native Selenium click)")
                except Exception as native_err:
                    # Fallback to ActionChains if native click was intercepted
                    logger.warning(
                        f"  Native click failed "
                        f"({type(native_err).__name__}) — trying ActionChains"
                    )
                    ActionChains(self.driver).move_to_element(auth_link).click().perform()
                    logger.info("  Drilldown clicked (ActionChains)")

                # Let T24 begin rendering the record view
                time.sleep(2)
                return

        raise NoSuchElementException(
            f"Customer ID '{customer_no}' was not found in the auth queue "
            f"({len(rows)} pending records inspected)."
        )
