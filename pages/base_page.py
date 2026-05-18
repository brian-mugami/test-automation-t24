import logging
from contextlib import contextmanager

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

logger = logging.getLogger(__name__)


class BasePage:
    DEFAULT_TIMEOUT = 30

    def __init__(self, driver: WebDriver, timeout: int = DEFAULT_TIMEOUT):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def open(self, url: str) -> None:
        logger.info(f"Navigating to {url}")
        self.driver.get(url)

    @property
    def current_url(self) -> str:
        return self.driver.current_url

    @property
    def title(self) -> str:
        return self.driver.title

    # ---------- Frame handling (T24 frameset support) ----------
    def switch_to_frame(self, locator: tuple) -> None:
        """Switch the WebDriver context into a frame."""
        frame = self.wait.until(EC.presence_of_element_located(locator))
        self.driver.switch_to.frame(frame)
        logger.info(f"Switched into frame: {locator}")

    def switch_to_default(self) -> None:
        """Return to the top-level document."""
        self.driver.switch_to.default_content()
        logger.info("Switched back to default content")

    @contextmanager
    def in_frame(self, locator: tuple):
        """Context manager: temporarily switch into a frame, then back out.

        Usage:
            with self.in_frame(self.MENU_FRAME):
                self.find(self.SOME_ELEMENT)
        """
        self.switch_to_frame(locator)
        try:
            yield
        finally:
            self.switch_to_default()

    # ---------- Element interactions ----------
    def find(self, locator: tuple) -> WebElement:
        """Wait for element to be present in DOM, then return it."""
        try:
            return self.wait.until(EC.presence_of_element_located(locator))
        except TimeoutException:
            logger.error(f"Element not found: {locator}")
            raise

    def find_visible(self, locator: tuple) -> WebElement:
        """Wait for element to be visible on screen."""
        try:
            return self.wait.until(EC.visibility_of_element_located(locator))
        except TimeoutException:
            logger.error(f"Element not visible: {locator}")
            raise

    def js_click(self, locator: tuple, timeout: int = 10) -> None:
        """Click an element via JavaScript execute_script.

        More reliable than native click() for T24 elements that use
        href='javascript:...' or onclick handlers — native clicks can
        fail silently under automation, but execute_script always fires.
        """
        element = WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        self.driver.execute_script("arguments[0].click();", element)

    def click(self, locator: tuple) -> None:
        """Wait for element to be clickable, then click. Resilient to stale elements."""
        last_error = None
        for attempt in range(3):
            try:
                element = self.wait.until(EC.element_to_be_clickable(locator))
                element.click()
                logger.info(f"Clicked: {locator}")
                return
            except StaleElementReferenceException as e:
                last_error = e
                logger.info(
                    f"Stale element on click {locator}, retrying "
                    f"(attempt {attempt + 1}/3)"
                )
            except TimeoutException:
                logger.error(f"Element not clickable: {locator}")
                raise
        raise last_error

    def type(self, locator: tuple, text: str, clear_first: bool = True) -> None:
        last_error = None
        for attempt in range(3):
            try:
                element = self.find_visible(locator)
                if clear_first:
                    element.clear()
                element.send_keys(text)
                logger.info(f"Typed into {locator}")
                return
            except StaleElementReferenceException as e:
                last_error = e
                logger.info(
                    f"Stale element on {locator}, retrying "
                    f"(attempt {attempt + 1}/3)"
                )
        # All retries exhausted
        raise last_error

    def get_text(self, locator: tuple) -> str:
        return self.find_visible(locator).text

    def is_visible(self, locator: tuple, timeout: int = 5) -> bool:
        """Check if element is visible without raising on failure."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_present(self, locator: tuple, timeout: int = 5) -> bool:
        """Check if element exists in DOM (may or may not be visible)."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def debug_dump(self, label: str = "debug"):
        """Diagnostic: print current frame context and save a labelled screenshot."""
        self.switch_to_default()
        top_frames = self.driver.find_elements(By.TAG_NAME, "frame") \
                     + self.driver.find_elements(By.TAG_NAME, "iframe")

        print(f"\n--- DEBUG: {label} ---")
        print(f"Window handles: {len(self.driver.window_handles)}")
        print(f"Top-level frames: {len(top_frames)}")
        for f in top_frames:
            fid = f.get_attribute("id") or "(no id)"
            name = f.get_attribute("name") or "(no name)"
            src = (f.get_attribute("src") or "")[:60]
            print(f"  - id={fid}, name={name}, src={src}")

        self.screenshot(f"DEBUG_{label}")
        print(f"--- end DEBUG: {label} ---\n")

    def switch_to_new_window(self, timeout: int = 10) -> None:
        original = self.driver.current_window_handle
        self.wait.until(lambda d: len(d.window_handles) > 1)
        new_handle = next(
            h for h in self.driver.window_handles if h != original
        )
        self.driver.switch_to.window(new_handle)

        # Maximize so toolbar / lower divs are reachable without scrolling
        try:
            self.driver.maximize_window()
        except Exception:
            pass

        logger.info(f"Switched to and maximized window: {new_handle}")
    # evidence#
    def screenshot(self, name: str) -> str:
        """Save a screenshot and return its path."""
        path = f"reports/screenshots/{name}.png"
        self.driver.save_screenshot(path)
        logger.info(f"Screenshot saved: {path}")
        return path



