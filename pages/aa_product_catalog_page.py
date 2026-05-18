import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from pages.base_page import BasePage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


class AAProductCatalogPage(BasePage):

    # Frame-discovery signals
    _CATALOG_MARKER = (By.XPATH, "//table[contains(@id,'datadisplay')]")
    NEW_ARRANGEMENT = (By.XPATH, "//a[@title='New Arrangement']")

    MAX_FRAME_DEPTH = 4

    # ---------------------------------------------------------------
    # Frame walking
    # ---------------------------------------------------------------
    def _search_frames(self, locator, depth):
        """Depth-first search of the frame tree for `locator`.
        Leaves the driver inside the matching frame when True."""
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
        """Walk every frame until `locator` is present. Raise on timeout."""
        end = time.time() + timeout
        while time.time() < end:
            self.driver.switch_to.default_content()
            if self._search_frames(locator, depth=0):
                return
            time.sleep(0.5)
        self.screenshot(f"DEBUG_aa_frame_not_found_{what}")
        raise T24TestError(
            what_happened=f"Could not locate the {what}",
            why=(f"Walked every frame for {timeout}s but found no element "
                 f"matching {locator[1]}."),
            how_to_fix=(f"Open DEBUG_aa_frame_not_found_{what}.png. If the "
                        "screen is visible the DOM moved; if not, the prior "
                        "navigation step did not complete."),
        )

    # ---------------------------------------------------------------
    # Locators built from visible labels
    # ---------------------------------------------------------------
    @staticmethod
    def _item_cell(item_name):
        return (By.XPATH,
                f"//td[contains(@class,'ENQ-DATA-ID') "
                f"and normalize-space(.)=\"{item_name}\"]")

    @staticmethod
    def _expand_link(group_name):
        # Matches only the COLLAPSED-state control (Expand-group icon).
        return (By.XPATH,
                f"//td[normalize-space(.)=\"{group_name}\"]"
                f"/a[contains(@href,'expandrow') "
                f"and .//img[@alt='Expand group']]")

    @staticmethod
    def _drilldown_link(item_name):
        return (By.XPATH,
                f"//tr[td[contains(@class,'ENQ-DATA-ID') "
                f"and normalize-space(.)=\"{item_name}\"]]"
                f"//td[contains(@class,'enqdrilldowncell')]/a")

    # ---------------------------------------------------------------
    # Public steps
    # ---------------------------------------------------------------
    def wait_for_catalog_loaded(self, timeout=30):
        """Block until the product-catalog enquiry tree is rendered."""
        self._switch_to_frame_with(self._CATALOG_MARKER,
                                   "product_catalog", timeout)
        logger.info("AA product catalog enquiry loaded")
        return self

    def open_group(self, group_name, item_name, timeout=15):
        """Expand `group_name` so `item_name` becomes interactable.

        Idempotent: if the item row is already visible, does nothing.
        """
        self._switch_to_frame_with(self._CATALOG_MARKER, "product_catalog")

        cells = self.driver.find_elements(*self._item_cell(item_name))
        if cells and any(c.is_displayed() for c in cells):
            logger.info(f"'{item_name}' already visible - group expanded")
            return self

        links = self.driver.find_elements(*self._expand_link(group_name))
        if not links:
            self.screenshot("DEBUG_aa_group_not_found")
            raise T24TestError(
                what_happened=f"Could not expand the '{group_name}' group",
                why=(f"No collapsed-state expand control for '{group_name}', "
                     f"and '{item_name}' is not visible."),
                how_to_fix=("Open DEBUG_aa_group_not_found.png and confirm "
                            f"'{group_name}' exists in the catalog tree."),
            )

        link = links[0]
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", link)
        time.sleep(0.3)
        link.click()  # native click - runs expandrow()
        logger.info(f"Expanded group '{group_name}'")

        end = time.time() + timeout
        while time.time() < end:
            cells = self.driver.find_elements(*self._item_cell(item_name))
            if cells and any(c.is_displayed() for c in cells):
                logger.info(f"'{item_name}' row now visible")
                return self
            time.sleep(0.4)

        self.screenshot("DEBUG_aa_item_not_visible")
        raise T24TestError(
            what_happened=f"'{item_name}' did not appear after expanding "
                          f"'{group_name}'",
            why="The expand click did not reveal the expected child row.",
            how_to_fix="Open DEBUG_aa_item_not_visible.png to inspect the tree.",
        )

    def drilldown_item(self, item_name, timeout=20):
        """Click the drilldown arrow on the named catalog row."""
        self._switch_to_frame_with(self._CATALOG_MARKER, "product_catalog")
        try:
            link = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(self._drilldown_link(item_name)))
        except TimeoutException:
            self.screenshot("DEBUG_aa_drilldown_missing")
            raise T24TestError(
                what_happened=f"No drilldown link for '{item_name}'",
                why=(f"Row '{item_name}' has no clickable drilldown arrow - "
                     "it may be a group header rather than a product line."),
                how_to_fix="Open DEBUG_aa_drilldown_missing.png to inspect.",
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", link)
        time.sleep(0.3)
        link.click()  # native click - drilldown() needs it
        logger.info(f"Drilled into '{item_name}'")
        time.sleep(2)  # enquiry frame reloads
        return self

    def wait_for_products_screen(self, timeout=30):
        """Block until the post-drilldown products screen (with the
        'New Arrangement' action) is rendered."""
        self._switch_to_frame_with(self.NEW_ARRANGEMENT,
                                   "products_screen", timeout)
        logger.info("Term Deposit products screen loaded")
        return self

    def click_new_arrangement(self, timeout=20):
        """Click 'New Arrangement' to launch the AA input screen."""
        self._switch_to_frame_with(self.NEW_ARRANGEMENT, "products_screen")
        try:
            link = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(self.NEW_ARRANGEMENT))
        except TimeoutException:
            self.screenshot("DEBUG_aa_new_arrangement_missing")
            raise T24TestError(
                what_happened="'New Arrangement' link not found",
                why="The products screen exposed no New Arrangement action.",
                how_to_fix=("Open DEBUG_aa_new_arrangement_missing.png and "
                            "confirm the drilldown landed on the product list."),
            )

        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", link)
        time.sleep(0.3)
        link.click()  # native click
        logger.info("Clicked 'New Arrangement' - launching AA input screen")
        time.sleep(3)
        return self