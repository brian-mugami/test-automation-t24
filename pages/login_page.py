from selenium.webdriver.common.by import By
from pages.base_page import BasePage
from pages.home_page import HomePage


class LoginPage(BasePage):

    # ---------- Locators ----------
    USERNAME_FIELD = (By.ID, "signOnName")
    PASSWORD_FIELD = (By.ID, "password")
    SIGN_IN_BUTTON = (By.ID, "sign-in")

    # ---------- Actions ----------
    def load(self, url: str) -> "LoginPage":
        self.open(url)
        self.find_visible(self.USERNAME_FIELD)  # wait for page to be ready
        return self

    def enter_username(self, username: str) -> "LoginPage":
        self.type(self.USERNAME_FIELD, username)
        return self

    def enter_password(self, password: str) -> "LoginPage":
        self.type(self.PASSWORD_FIELD, password)
        return self

    def click_sign_in(self) -> HomePage:
        self.click(self.SIGN_IN_BUTTON)
        return HomePage(self.driver)

    def login(self, username: str, password: str) -> HomePage:
        """High-level method tests will usually call."""
        return (
            self.enter_username(username)
                .enter_password(password)
                .click_sign_in()
        )