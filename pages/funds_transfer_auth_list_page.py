"""T24 FUNDS.TRANSFER auth queue — list of FTs pending authorisation."""
import logging
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class FundsTransferAuthListPage(BasePage):
    """Page object for the FUNDS.TRANSFER unauthorised enquiry.

    FT ID lives in column 1 of each row (matches CUSTOMER.NAU layout).
    We pin to any data row containing an Authorise link inside the
    enquiry data table — class names vary slightly between T24 builds.
    """

    PENDING_ROWS = (
        By.XPATH,
        "//table[contains(@class, 'enquirydata')]"
        "//tr[.//a[@title='Authorise']]"
    )

    def _wait_for_list_loaded(self, timeout: int = 15) -> None:
        try:
            self.wait.until(
                lambda d: len(d.find_elements(*self.PENDING_ROWS)) > 0
            )
        except TimeoutException:
            raise TimeoutException(
                f"FT auth queue did not load any rows within {timeout}s."
            )

    def list_pending_ft_ids(self) -> list:
        """Return FT IDs from column 1 of each pending row."""
        self._wait_for_list_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)
        ids = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue
            ids.append(cells[0].text.strip())
        return ids

    def is_record_listed(self, ft_id: str) -> bool:
        try:
            return ft_id in self.list_pending_ft_ids()
        except TimeoutException:
            return False

    def click_authorise_for(self, ft_id: str) -> None:
        """Find row by column-1 FT ID and click its drilldown."""
        self._wait_for_list_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)

        logger.info(f"Searching {len(rows)} pending FTs for ID '{ft_id}'")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue
            if cells[0].text.strip() == ft_id:
                logger.info(f"  ✓ Match: {ft_id}")
                auth_link = row.find_element(By.XPATH, ".//a[@title='Authorise']")

                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", auth_link
                )
                time.sleep(0.5)
                try:
                    auth_link.click()
                    logger.info("  Drilldown clicked (native)")
                except Exception:
                    ActionChains(self.driver).move_to_element(auth_link).click().perform()
                    logger.info("  Drilldown clicked (ActionChains)")
                time.sleep(2)
                return

        raise NoSuchElementException(
            f"FT ID '{ft_id}' not found in auth queue "
            f"({len(rows)} pending records inspected)."
        )