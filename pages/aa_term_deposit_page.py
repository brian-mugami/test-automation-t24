import logging
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import TimeoutException

from pages.base_page import BasePage
from utils.exceptions import T24TestError

logger = logging.getLogger(__name__)


class AATermDepositPage(BasePage):

    MAX_FRAME_DEPTH = 5

    # ---- form fields (form frame) ----
    CUSTOMER       = (By.ID, "fieldName:CUSTOMER:1")
    CURRENCY       = (By.ID, "fieldName:CURRENCY")
    PAYIN_ACCOUNT  = (By.ID, "fieldName:PAYIN.ACCOUNT:1:1")
    PAYOUT_ACCOUNT = (By.ID, "fieldName:PAYOUT.ACCOUNT:1:1")
    ARRANGEMENT_ID     = (By.ID, "disabled_ARRANGEMENT")
    ARRANGEMENT_HIDDEN = (By.ID, "fieldName:ARRANGEMENT")
    ARR_ID_PATTERN = re.compile(r"AA\d{5}[A-Z0-9]{3,9}")

    # ---- toolbar (toolbar frame) ----
    VALIDATE_BTN = (By.CSS_SELECTOR, "a[accesskey='V'][title='Validate a deal']")
    COMMIT_BTN   = (By.CSS_SELECTOR, "a[accesskey='C'][title='Commit the deal']")

    # ---- commit-time prompts ----
    WARNING_SELECT   = (By.CSS_SELECTOR, "select.warningbox")
    ACCEPT_OVERRIDES = (By.ID, "errorImg")

    # ---------------------------------------------------------------
    # Frame walking
    # ---------------------------------------------------------------
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
        """Walk every frame until `locator` is present. Returns bool."""
        end = time.time() + timeout
        while time.time() < end:
            self.driver.switch_to.default_content()
            if self._search_frames(locator, depth=0):
                return True
            time.sleep(0.5)
        return False

    def _require_frame(self, locator, what, timeout=25):
        if not self._switch_to_frame_with(locator, what, timeout):
            self.screenshot(f"DEBUG_aa_{what}_frame_not_found")
            raise T24TestError(
                what_happened=f"Could not locate the {what}",
                why=(f"Walked every frame for {timeout}s; no element "
                     f"matched {locator[1]}."),
                how_to_fix=(f"Open DEBUG_aa_{what}_frame_not_found.png. If the "
                            "screen is visible the DOM moved; if not, the "
                            "previous step did not complete."),
            )

    # ---------------------------------------------------------------
    # Low-level helpers
    # ---------------------------------------------------------------
    def _click(self, locator, label, timeout=15):
        try:
            el = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(locator))
        except TimeoutException:
            self.screenshot(f"DEBUG_aa_click_{label}")
            raise T24TestError(
                what_happened=f"Could not click '{label}'",
                why=f"{locator[1]} was not clickable within {timeout}s.",
                how_to_fix=f"Open DEBUG_aa_click_{label}.png to inspect.",
            )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.3)
        try:
            el.click()
        except Exception as e:
            logger.warning(f"Native click on '{label}' failed "
                            f"({type(e).__name__}) - using execute_script")
            self.driver.execute_script("arguments[0].click();", el)

    def _blur_active(self):
        """Blur the focused field so its T24 onblur (checkfile / refresh)
        fires before the next action."""
        try:
            self.driver.execute_script(
                "if(document.activeElement && document.activeElement.blur)"
                "document.activeElement.blur();")
        except Exception:
            pass

    # ---------------------------------------------------------------
    # Public steps
    # ---------------------------------------------------------------
    def wait_for_form_loaded(self, timeout=30):
        """Block until the AA arrangement form (tab1) is rendered."""
        self._require_frame(self.CUSTOMER, "form", timeout)
        logger.info("AA Term Deposit input form loaded")
        return self

    def fill_initial_fields(self, customer, currency):
        """Fill the two header fields required before first validation."""
        self._require_frame(self.CUSTOMER, "form")
        self.type(self.CUSTOMER, str(customer))

        # CURRENCY is a hot-validate field; type() retries on stale.
        self._require_frame(self.CURRENCY, "form")
        self.type(self.CURRENCY, currency)

        self._blur_active()      # fire CURRENCY checkfile / refresh
        time.sleep(1.5)
        logger.info(f"Filled Customer={customer}, Currency={currency}")
        return self

    def validate(self):
        """Click the Validate toolbar button."""
        self._require_frame(self.VALIDATE_BTN, "toolbar")
        self._click(self.VALIDATE_BTN, "Validate")
        logger.info("Validate triggered")
        time.sleep(2)
        return self

    def wait_for_settlement_fields(self, timeout=30):
        """After the first Validate, wait for the pay-in / pay-out account
        fields that T24 renders for the deposit settlement schedule."""
        if not self._switch_to_frame_with(self.PAYIN_ACCOUNT,
                                          "settlement", timeout):
            self.screenshot("DEBUG_aa_settlement_fields_missing")
            raise T24TestError(
                what_happened="Pay-in / pay-out account fields did not appear",
                why=("The first Validate did not render the deposit "
                     "settlement fields within the timeout."),
                how_to_fix=("Open DEBUG_aa_settlement_fields_missing.png. If a "
                            "validation error is shown, the Customer or "
                            "Currency value was rejected."),
            )
        logger.info("Settlement fields (PAYIN / PAYOUT) rendered")
        return self

    def fill_settlement_accounts(self, payin, payout):
        """Fill the pay-in and pay-out account fields."""
        self._require_frame(self.PAYIN_ACCOUNT, "settlement")
        self.type(self.PAYIN_ACCOUNT, str(payin))
        self._require_frame(self.PAYOUT_ACCOUNT, "settlement")
        self.type(self.PAYOUT_ACCOUNT, str(payout))
        self._blur_active()
        time.sleep(1)
        logger.info(f"Filled PAYIN.ACCOUNT={payin}, PAYOUT.ACCOUNT={payout}")
        return self

    def commit(self):
        """Click the Commit toolbar button."""
        self._require_frame(self.COMMIT_BTN, "toolbar")
        self._click(self.COMMIT_BTN, "Commit")
        logger.info("Commit triggered")
        time.sleep(3)
        return self

    def answer_warnings(self, answer="RECEIVED", timeout=20):
        """Answer commit-time warning question(s).

        T24 raises one or more <select class="warningbox"> questions
        (e.g. 'Have you received Deposit Agreement...'). Sets every chooser
        that offers `answer`, firing change so changeWarning() records it.
        Returns the count answered.
        """
        if not self._switch_to_frame_with(self.WARNING_SELECT,
                                           "warning", timeout):
            logger.info("No warning chooser appeared after commit")
            return 0

        time.sleep(0.5)
        selects = self.driver.find_elements(*self.WARNING_SELECT)
        answered = 0
        for sel in selects:
            try:
                values = [o.get_attribute("value")
                          for o in sel.find_elements(By.TAG_NAME, "option")]
                if answer not in values:
                    continue
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", sel)
                Select(sel).select_by_value(answer)
                # Belt-and-braces: ensure changeWarning() fires.
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change',"
                    "{bubbles:true}));", sel)
                answered += 1
                logger.info(f"Answered a warning chooser with '{answer}'")
            except Exception as e:
                logger.warning(f"Could not set a warning chooser: {e}")
        time.sleep(2)
        return answered

    def has_overrides_popup(self, wait_seconds=10.0):
        """Whether the 'Accept Overrides' link is present."""
        return self._switch_to_frame_with(self.ACCEPT_OVERRIDES,
                                           "override", timeout=wait_seconds)

    def accept_overrides(self, timeout=15):
        """Click 'Accept Overrides' to finalise the commit."""
        if not self._switch_to_frame_with(self.ACCEPT_OVERRIDES,
                                          "override", timeout):
            self.screenshot("DEBUG_aa_overrides_missing")
            raise T24TestError(
                what_happened="'Accept Overrides' link not found",
                why="No override-acknowledgement link appeared after commit.",
                how_to_fix="Open DEBUG_aa_overrides_missing.png to inspect.",
            )
        self._click(self.ACCEPT_OVERRIDES, "AcceptOverrides")
        logger.info("Accept Overrides clicked - commit finalised")
        time.sleep(3)
        return self

    def _find_arrangement_in_frames(self, depth=0):
        try:
            for el in self.driver.find_elements(*self.ARRANGEMENT_ID):
                t = (el.get_attribute("textContent") or "").strip()
                if t and t.upper() != "NEW":
                    logger.info(f"Arrangement ID from disabled_ARRANGEMENT: {t}")
                    return t
        except Exception:
            pass
        try:
            for el in self.driver.find_elements(*self.ARRANGEMENT_HIDDEN):
                v = (el.get_attribute("value") or "").strip()
                if v and v.upper() != "NEW":
                    logger.info(f"Arrangement ID from hidden field: {v}")
                    return v
        except Exception:
            pass
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            hits = self.ARR_ID_PATTERN.findall(
                body.get_attribute("textContent") or "")
            if hits:
                logger.info(f"Arrangement ID from page-text scan: {hits[0]} "
                            f"(all hits: {sorted(set(hits))})")
                return hits[0]
        except Exception:
            pass

        if depth >= self.MAX_FRAME_DEPTH:
            return None
        count = (len(self.driver.find_elements(By.TAG_NAME, "frame"))
                 + len(self.driver.find_elements(By.TAG_NAME, "iframe")))
        for i in range(count):
            try:
                frames = (self.driver.find_elements(By.TAG_NAME, "frame")
                          + self.driver.find_elements(By.TAG_NAME, "iframe"))
                if i >= len(frames):
                    break
                self.driver.switch_to.frame(frames[i])
                found = self._find_arrangement_in_frames(depth + 1)
                if found:
                    return found
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    self.driver.switch_to.default_content()
        return None

    def read_arrangement_id(self, timeout=45):
        end = time.time() + timeout
        while time.time() < end:
            for handle in list(self.driver.window_handles):
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.switch_to.default_content()
                except Exception:
                    continue
                found = self._find_arrangement_in_frames(depth=0)
                if found:
                    return found
            time.sleep(1)

        self._dump_post_commit_state()
        return None

    def _dump_post_commit_state(self):
        """Log a detailed snapshot of every window/frame after commit."""
        logger.warning("================ POST-COMMIT DIAGNOSTIC ================")
        try:
            handles = list(self.driver.window_handles)
        except Exception as e:
            logger.warning(f"Could not list windows: {e}")
            return
        logger.warning(f"Open windows: {len(handles)}")
        for wi, handle in enumerate(handles):
            try:
                self.driver.switch_to.window(handle)
                self.driver.switch_to.default_content()
                logger.warning(f"--- Window {wi}: title={self.driver.title!r} "
                               f"url={self.driver.current_url[:140]!r}")
                self._dump_frame_tree(wi, "root", depth=0)
            except Exception as e:
                logger.warning(f"--- Window {wi}: inspection failed ({e})")
        logger.warning("============== END POST-COMMIT DIAGNOSTIC ==============")

    def _dump_frame_tree(self, wi, path, depth):
        """Log diagnostic content for the current frame, then recurse."""
        prefix = f"  [w{wi} {path}]"
        try:
            for el in self.driver.find_elements(*self.ARRANGEMENT_ID):
                logger.warning(f"{prefix} disabled_ARRANGEMENT textContent="
                               f"{(el.get_attribute('textContent') or '')!r}")
        except Exception:
            pass
        try:
            for el in self.driver.find_elements(*self.ARRANGEMENT_HIDDEN):
                logger.warning(f"{prefix} fieldName:ARRANGEMENT value="
                               f"{(el.get_attribute('value') or '')!r}")
        except Exception:
            pass
        try:
            for el in self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "td.message, .message, #message, .errortext"):
                txt = (el.get_attribute("textContent") or "").strip()
                if txt:
                    logger.warning(f"{prefix} message={txt[:220]!r}")
        except Exception:
            pass
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body_text = body.get_attribute("textContent") or ""
            hits = sorted(set(self.ARR_ID_PATTERN.findall(body_text)))
            if hits:
                logger.warning(f"{prefix} AA-id pattern hits: {hits}")
            snippet = " ".join(body_text.split())[:280]
            if snippet:
                logger.warning(f"{prefix} body text: {snippet!r}")
        except Exception:
            pass

        if depth >= self.MAX_FRAME_DEPTH:
            return
        count = (len(self.driver.find_elements(By.TAG_NAME, "frame"))
                 + len(self.driver.find_elements(By.TAG_NAME, "iframe")))
        for i in range(count):
            try:
                frames = (self.driver.find_elements(By.TAG_NAME, "frame")
                          + self.driver.find_elements(By.TAG_NAME, "iframe"))
                if i >= len(frames):
                    break
                self.driver.switch_to.frame(frames[i])
                self._dump_frame_tree(wi, f"{path}.{i}", depth + 1)
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    self.driver.switch_to.default_content()
