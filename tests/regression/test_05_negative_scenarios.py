"""Negative & compliance scenarios.

These tests are designed to expose validation gaps. They:
  1. Perform a known-problematic input scenario.
  2. Capture screenshots throughout.
  3. Assert that T24 should have rejected the record.
  4. FAIL — with a business-readable explanation — if T24 accepts it.

A test failing here is the framework working as intended: it caught
something the bank's T24 configuration missed.
"""
import logging
import os

import pytest

from pages.login_page import LoginPage
from pages.individual_customer_page import IndividualCustomerPage
from utils.exceptions import T24TestError
from utils.test_data import generate_customer_data

logger = logging.getLogger(__name__)


# ============================================================
# SCENARIO 1 — Title MR with Gender FEMALE (the headline demo)
# ============================================================

@pytest.mark.negative
def test_compliance_title_mr_with_female_gender(driver, config):
    """Compliance: Title 'MR' with Gender 'FEMALE' is inconsistent.

    T24's default configuration does not cross-validate TITLE against
    GENDER. A record with Title='MR' (which implies male) and
    Gender='FEMALE' represents a data-quality compliance gap.

    Expected outcome: TEST FAILS — exposing the gap with a screenshot
    showing T24 accepted the inconsistent record.
    """
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened=f"Could not sign in as INPUTTER "
                          f"'{config['inputter']['username']}'",
            why="The T24 home page did not appear after login.",
            how_to_fix="Confirm INPUTTER credentials and T24 availability.",
        )

    home.open_individual_customer_by_command()
    home.switch_to_new_window()

    # Deliberately inconsistent: MR + FEMALE
    customer = generate_customer_data(title="Mr")
    customer["title"] = "MR"
    customer["gender"] = "FEMALE"

    customer_page = IndividualCustomerPage(driver)
    customer_page.build_mnemonic(customer)
    logger.info(
        f"Compliance test: creating customer with Title='MR' / Gender='FEMALE' "
        f"(mnemonic {customer['mnemonic']})"
    )

    customer_page.fill_customer_tab(customer)
    customer_page.screenshot("01_mr_with_female_filled")   # The smoking gun
    customer_page.fill_physical_address_tab(customer)
    customer_page.fill_contact_details_tab(customer)
    customer_page.screenshot("02_all_tabs_filled")

    customer_page.validate()
    customer_page.wait_for_transaction_result(timeout=5)
    customer_page.screenshot("03_validation_outcome")
    val_result = customer_page.get_transaction_result()

    if val_result["status"] == "error":
        logger.info(
            f"✓ T24 correctly rejected at validation: {val_result['message']}"
        )
        return  # T24 has a validation rule — compliance gap is closed

    # Validation passed — try to commit
    customer_page.commit()
    customer_page.wait_for_transaction_result(timeout=10)
    customer_page.screenshot("04_commit_outcome")
    commit_result = customer_page.get_transaction_result()

    if commit_result["status"] == "success":
        # T24 accepted the inconsistent record — compliance gap exposed
        raise T24TestError(
            what_happened=(
                "Title/Gender inconsistency was NOT detected by T24. "
                "A customer record with Title='MR' and Gender='FEMALE' "
                f"was accepted (customer ID {commit_result['transaction_id']})."
            ),
            why=(
                "T24's default validation does not cross-check the TITLE "
                "field against the GENDER field. Title='MR' (which implies "
                "male) was accepted alongside Gender='FEMALE' without any "
                "warning or rejection. This represents a compliance "
                "configuration gap that could allow inconsistent customer "
                "data into the bank's master records — potentially "
                "affecting reporting, KYC, and downstream integrations."
            ),
            how_to_fix=(
                "Either: (a) configure a TITLE-vs-GENDER consistency rule "
                "at the T24 STORE.CONTROL.UPDATE level for the CUSTOMER "
                "application, OR (b) document this as a known gap and "
                "route detection to the bank's downstream data quality "
                "monitoring pipeline."
            ),
        )

    # Commit was rejected — T24 has a deeper validation
    logger.info(
        f"✓ T24 rejected at commit: {commit_result['message']}"
    )


# ============================================================
# SCENARIO 2 — Date of Birth in the future
# ============================================================
@pytest.mark.negative
def test_compliance_future_date_of_birth(driver, config):
    """Compliance: DOB in the future is logically impossible.

    A customer cannot have been born after today. T24 should reject
    any DOB > today's business date.
    """
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened="Could not sign in as INPUTTER",
            why="Home page did not appear.",
            how_to_fix="Confirm credentials.",
        )

    home.open_individual_customer_by_command()
    home.switch_to_new_window()

    customer = generate_customer_data(title="Mr")
    customer["date_of_birth"] = "01 JAN 2035"   # Future date

    customer_page = IndividualCustomerPage(driver)
    customer_page.build_mnemonic(customer)
    logger.info(
        f"Compliance test: creating customer with DOB in 2035 "
        f"(mnemonic {customer['mnemonic']})"
    )

    customer_page.fill_customer_tab(customer)
    customer_page.screenshot("01_future_dob_filled")
    customer_page.fill_physical_address_tab(customer)
    customer_page.fill_contact_details_tab(customer)

    customer_page.validate()
    customer_page.wait_for_transaction_result(timeout=5)
    customer_page.screenshot("02_validation_outcome")
    val_result = customer_page.get_transaction_result()

    if val_result["status"] == "error":
        logger.info(
            f"✓ T24 correctly rejected the future DOB: {val_result['message']}"
        )
        return

    customer_page.commit()
    customer_page.wait_for_transaction_result(timeout=10)
    customer_page.screenshot("03_commit_outcome")
    commit_result = customer_page.get_transaction_result()

    if commit_result["status"] == "success":
        raise T24TestError(
            what_happened=(
                "Customer record with DOB in 2035 was accepted by T24 "
                f"(customer ID {commit_result['transaction_id']})."
            ),
            why=(
                "T24 accepted a Date of Birth in the future. This violates "
                "basic temporal validity — a customer cannot be born after "
                "today's business date. The record was committed without "
                "any age-validity check."
            ),
            how_to_fix=(
                "Configure DOB validation at the field level for the "
                "CUSTOMER application — REQUIRE DOB <= TODAY."
            ),
        )

    logger.info(f"✓ T24 rejected at commit: {commit_result['message']}")


# ============================================================
# SCENARIO 3 — Invalid nationality code
# ============================================================
@pytest.mark.negative
def test_negative_invalid_nationality_code(driver, config):
    """Negative: NATIONALITY='ZZ' is not a valid ISO country code.

    T24 should reject this via its COUNTRY lookup validation.
    """
    home = (
        LoginPage(driver)
        .load(config["url"])
        .login(**config["inputter"])
    )
    if not home.is_loaded():
        raise T24TestError(
            what_happened="Could not sign in as INPUTTER",
            why="Home page did not appear.",
            how_to_fix="Confirm credentials.",
        )

    home.open_individual_customer_by_command()
    home.switch_to_new_window()

    customer = generate_customer_data(title="Mr")
    customer["nationality"] = "ZZ"   # Invalid country code

    customer_page = IndividualCustomerPage(driver)
    customer_page.build_mnemonic(customer)
    logger.info(
        f"Negative test: creating customer with NATIONALITY='ZZ' "
        f"(mnemonic {customer['mnemonic']})"
    )

    customer_page.fill_customer_tab(customer)
    customer_page.screenshot("01_invalid_nationality_filled")

    customer_page.validate()
    customer_page.wait_for_transaction_result(timeout=5)
    customer_page.screenshot("02_validation_outcome")
    val_result = customer_page.get_transaction_result()

    if val_result["status"] == "error":
        logger.info(
            f"✓ T24 correctly rejected invalid nationality: {val_result['message']}"
        )
        return   # Test passes — T24 validation works

    # Validation passed — try to commit
    customer_page.fill_physical_address_tab(customer)
    customer_page.fill_contact_details_tab(customer)
    customer_page.commit()
    customer_page.wait_for_transaction_result(timeout=10)
    customer_page.screenshot("03_commit_outcome")
    commit_result = customer_page.get_transaction_result()

    if commit_result["status"] == "success":
        raise T24TestError(
            what_happened=(
                f"Customer with NATIONALITY='ZZ' (invalid code) was "
                f"accepted (customer ID {commit_result['transaction_id']})."
            ),
            why=(
                "T24 accepted a non-existent country code in the "
                "NATIONALITY field. The COUNTRY lookup validation "
                "should have caught this at field entry."
            ),
            how_to_fix=(
                "Verify the COUNTRY lookup table is properly linked to "
                "the NATIONALITY field in CUSTOMER application."
            ),
        )

    logger.info(f"✓ T24 rejected at commit: {commit_result['message']}")