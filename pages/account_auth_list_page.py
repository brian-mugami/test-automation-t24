import logging
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class AccountAuthListPage(BasePage):
    PENDING_ROWS = (
        By.XPATH,
        "//tr[contains(@class, 'ACCOUNTNAU') and .//a[@title='Authorise']]"
    )

    def _wait_for_list_loaded(self, timeout: int = 15) -> None:
        try:
            self.wait.until(
                lambda d: len(d.find_elements(*self.PENDING_ROWS)) > 0
            )
        except TimeoutException:
            raise TimeoutException(
                f"The account auth queue did not load any rows within {timeout}s."
            )

    def list_pending_account_ids(self) -> list:
        self._wait_for_list_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)

        ids = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 2:
                logger.warning(
                    f"Skipping row id='{row.get_attribute('id') or '?'}' — "
                    f"only {len(cells)} cell(s), expected at least 2"
                )
                continue
            ids.append(cells[1].text.strip())
        return ids

    def is_record_listed(self, account_id: str) -> bool:
        try:
            return account_id in self.list_pending_account_ids()
        except TimeoutException:
            return False

    def click_authorise_for(self, account_id: str) -> None:
        """Find the row by column-2 value and click its Authorise drilldown."""
        self._wait_for_list_loaded()
        rows = self.driver.find_elements(*self.PENDING_ROWS)

        logger.info(
            f"Searching {len(rows)} pending accounts for account ID '{account_id}'"
        )

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 2:
                continue  # skip non-data rows defensively

            cell_value = cells[1].text.strip()
            if cell_value == account_id:
                logger.info(f"  ✓ Match: {cell_value}")
                auth_link = row.find_element(By.XPATH, ".//a[@title='Authorise']")

                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", auth_link
                )
                time.sleep(0.5)

                try:
                    auth_link.click()
                    logger.info("  Drilldown clicked (native Selenium click)")
                except Exception as native_err:
                    logger.warning(
                        f"  Native click failed "
                        f"({type(native_err).__name__}) — trying ActionChains"
                    )
                    ActionChains(self.driver).move_to_element(auth_link).click().perform()
                    logger.info("  Drilldown clicked (ActionChains)")

                time.sleep(2)
                return

        raise NoSuchElementException(
            f"Account ID '{account_id}' was not found in the auth queue "
            f"({len(rows)} pending records inspected)."
        )