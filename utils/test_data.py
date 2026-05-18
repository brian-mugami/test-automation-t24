"""Test data generators for T24 customer scenarios."""
import random
import string
from typing import Literal

import re
from faker import Faker

fake = Faker()

FIXED_VALUES = {
    "sector": "1001",
    "nationality": "RW",
    "residence": "RW",
    "cust_birth_country": "RW",
    "cust_birth_city": "Kigali",
    "language": "1",
    "account_officer": "1",
    "target": "999",
    "industry": "1000",
    "customer_status": "1",
}

# Realistic Kigali street names (KN/KG/KK prefixes are the actual naming
# convention in Kigali) and the three Kigali districts.
_KIGALI_STREETS = [
    "KN 4 Avenue", "KG 11 Avenue", "KN 7 Road",
    "KG 5 Street", "KK 19 Avenue", "KN 3 Road",
]
_KIGALI_DISTRICTS = ["Nyarugenge", "Gasabo", "Kicukiro"]


def _random_short_name(length: int = 3) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=length))


def _slug_for_email(text: str) -> str:
    """Strip anything that isn't alphanumeric so the email is always valid
    even if Faker returns names with hyphens, apostrophes, or accents."""
    return re.sub(r"[^a-zA-Z0-9]", "", text).lower()


def _generate_contact_details(given_name: str, family_name: str) -> dict:
    """Generate Rwandan contact details linked to the customer's name.

    Rwanda mobile numbers start with 078/079/072/073 (after the 0 prefix).
    The IDD prefix field (250) holds the country code separately, so the
    phone fields here use the local 10-digit format.
    """
    mobile_prefix = random.choice(["78", "79", "72", "73"])
    phone_mobile = f"0{mobile_prefix}{random.randint(1000000, 9999999)}"

    # Kigali fixed-line numbers start with 0252
    phone_home = f"0252{random.randint(100000, 999999)}"

    email = (
        f"{_slug_for_email(given_name)}."
        f"{_slug_for_email(family_name)}@yahoo.com"
    )

    return {
        "phone_home": phone_home,
        "phone_mobile": phone_mobile,
        "email": email,
        "idd_prefix": "250",  # Rwanda
    }


def _generate_rwanda_address() -> dict:
    """Plausible Kigali address."""
    return {
        "address_country": "RW",
        "address_type": "HOME",  # Residential
        "address_purpose": "CTC",  # Communication To Customer
        "building_number": str(random.randint(1, 200)),
        "street": random.choice(_KIGALI_STREETS),
        "town_city": "Kigali",
        "post_code": f"00{random.randint(100, 999)}",
        "district_name": random.choice(_KIGALI_DISTRICTS),
        "country": "RW",
    }


def generate_customer_data(title: Literal["Mr", "Mrs"] = "Mr") -> dict:
    """Generate a complete random customer profile with title-appropriate
    gender and a Rwandan address.

    The mnemonic is NOT set here — it's built from the T24-assigned
    transaction ID once the page opens.
    """
    is_male = title.upper() == "MR"
    given_name = fake.first_name_male() if is_male else fake.first_name_female()
    family_name = fake.last_name()

    return {
        # ---- Customer tab ----
        "title": "MR" if is_male else "MRS",
        "given_name": given_name,
        "family_name": family_name,
        "gb_full_name": f"{given_name} {family_name}",
        "gb_short_name": _random_short_name(),
        "gender": "MALE" if is_male else "FEMALE",
        "mnemonic": None,
        "date_of_birth": fake.date_of_birth(minimum_age=25, maximum_age=65)
        .strftime("%d %b %Y").upper(),
        **FIXED_VALUES,
        # ---- Physical Address tab ----
        **_generate_rwanda_address(),
        # ---- Contact Details tab ----
        **_generate_contact_details(given_name, family_name),
    }


def generate_account_mnemonic() -> str:
    first = random.choice(string.ascii_uppercase)
    digits = f"{random.randint(0, 9999):04d}"
    last = random.choice(string.ascii_uppercase)
    return f"{first}{digits}{last}"


def generate_account_data(customer: dict) -> dict:
    return {
        "customer_no": customer["customer_no"],
        "mnemonic": generate_account_mnemonic(),
        "account_title": customer["gb_full_name"],  # e.g. "Kenneth Patrick"
        "short_title": customer["gb_short_name"],  # e.g. "KYR"
    }
