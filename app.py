import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load variables from .env into os.environ
load_dotenv()

URL = os.getenv("BW_URL")
USERNAME = os.getenv("BW_USER")
PASSWORD = os.getenv("BW_PASS")

# Fail fast if anything is missing — saves debugging time later
if not all([URL, USERNAME, PASSWORD]):
    raise EnvironmentError(
        "Missing one or more required env vars: BW_URL, BW_USER, BW_PASS. "
        "Check your .env file."
    )

# Configure Chrome
options = Options()
options.add_argument("--start-maximized")
options.add_experimental_option("detach", True)
options.add_argument("--ignore-certificate-errors")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    driver.get(URL)

    username_field = wait.until(EC.presence_of_element_located((By.ID, "signOnName")))
    username_field.clear()
    username_field.send_keys(USERNAME)

    password_field = driver.find_element(By.ID, "password")
    password_field.clear()
    password_field.send_keys(PASSWORD)

    sign_in_btn = wait.until(EC.element_to_be_clickable((By.ID, "sign-in")))
    sign_in_btn.click()

    # Wait for URL to change after login
    wait.until(lambda d: d.current_url != URL)

    print(f"Logged in. Current URL: {driver.current_url}")
    print(f"Page title: {driver.title}")

except Exception as e:
    print(f"Something went wrong: {e}")