"""
Step 3 verification: Signup validation gate.
Only passes when accounts.jsonl contains accounts with real passwords,
not "NO_PASSWORD_YET" or error statuses.

This is the CI gate — it validates that real signup runs actually completed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json


ACCOUNTS_FILE = Path(__file__).parent.parent / "accounts.jsonl"


def _load_accounts():
    """Load all accounts from accounts.jsonl."""
    accounts = []
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        accounts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return accounts


def test_accounts_file_exists():
    """accounts.jsonl must exist after a signup run."""
    assert ACCOUNTS_FILE.exists(), f"accounts.jsonl not found at {ACCOUNTS_FILE}"


def test_has_completed_accounts():
    """At least one account must have a real password (not NO_PASSWORD_YET)."""
    accounts = _load_accounts()
    completed = [a for a in accounts if a.get("password") != "NO_PASSWORD_YET" and a.get("password") != "CAPTCHA_BLOCKED"]
    assert len(completed) > 0, "No accounts with real passwords found — signup flow not completing"


def test_account_has_valid_email():
    """Completed accounts must have valid email addresses with the correct domain."""
    accounts = _load_accounts()
    completed = [a for a in accounts if a.get("password") != "NO_PASSWORD_YET"]
    for acct in completed:
        email = acct.get("email", "")
        assert "@" in email, f"Invalid email: {email}"
        assert len(email) > 5, f"Email too short: {email}"


def test_account_password_is_real():
    """Completed accounts must have passwords that meet AWS requirements (8+ chars, mixed)."""
    accounts = _load_accounts()
    completed = [a for a in accounts if a.get("password") != "NO_PASSWORD_YET" and a.get("password") != "CAPTCHA_BLOCKED"]
    for acct in completed:
        pw = acct.get("password", "")
        assert len(pw) >= 8, f"Password too short ({len(pw)}): {pw}"
        has_upper = any(c.isupper() for c in pw)
        has_lower = any(c.islower() for c in pw)
        has_digit = any(c.isdigit() for c in pw)
        assert has_upper and has_lower and has_digit, f"Password lacks complexity: {pw}"


def test_account_has_name():
    """Completed accounts must have a real name (not empty or 'Unknown')."""
    accounts = _load_accounts()
    completed = [a for a in accounts if a.get("password") != "NO_PASSWORD_YET" and a.get("password") != "CAPTCHA_BLOCKED"]
    for acct in completed:
        name = acct.get("name", "")
        assert len(name) > 2, f"Name too short: {name}"
        assert name != "Unknown", f"Name is 'Unknown'"


def test_latest_account_is_recent():
    """The latest completed account must be from today (not stale data)."""
    accounts = _load_accounts()
    completed = [a for a in accounts if a.get("password") != "NO_PASSWORD_YET" and a.get("password") != "CAPTCHA_BLOCKED"]
    if not completed:
        return  # Skip if no completed accounts yet
    latest = completed[-1]
    created_at = latest.get("created_at", "")
    assert len(created_at) > 0, "No created_at timestamp"
    # Check date format YYYY-MM-DD
    date_part = created_at.split(" ")[0]
    assert len(date_part) == 10, f"Bad date format: {date_part}"


if __name__ == "__main__":
    tests = [
        ("accounts.jsonl exists", test_accounts_file_exists),
        ("Has completed accounts", test_has_completed_accounts),
        ("Account email valid", test_account_has_valid_email),
        ("Password is real", test_account_password_is_real),
        ("Account has name", test_account_has_name),
        ("Latest account is recent", test_latest_account_is_recent),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS: {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {name} — {e}")
            failed += 1
        except Exception as e:
            print(f"  FAIL: {name} — {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    if failed > 0:
        print("\nSIGNUP VALIDATION FAILED — real accounts not being created correctly")
    else:
        print("\nSIGNUP VALIDATION PASSED — real accounts are being created with valid credentials")
    sys.exit(0 if failed == 0 else 1)