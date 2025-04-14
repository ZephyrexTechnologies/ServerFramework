import random
import secrets
import string


def generate_test_email():
    """Generate a random test email."""
    random_string = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=10)
    ).lower()
    return f"{random_string}@test.com"


def generate_secure_password():
    """Generate a secure random password for testing."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(chars) for _ in range(12)) + "A1!"
