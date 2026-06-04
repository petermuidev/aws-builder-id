"""
Step 1 verification: Email service (Cloudflare Worker API)
Only passes if the real API responds correctly — no mocks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
import time
import requests

from config import EMAIL_WORKER_URL, EMAIL_DOMAIN, EMAIL_PREFIX_LENGTH


def test_worker_reachable():
    """Worker must respond to a health ping."""
    resp = requests.get(f"{EMAIL_WORKER_URL}/", timeout=15)
    assert resp.status_code in (200, 404), f"Worker unreachable: {resp.status_code}"


def test_create_temp_email():
    """Create a real temp email and verify we get address + JWT."""
    from services.email_service import create_temp_email

    email_address, jwt_token = create_temp_email()
    assert email_address is not None, "create_temp_email returned None"
    assert jwt_token is not None, "create_temp_email returned no JWT"
    assert EMAIL_DOMAIN in email_address, f"Domain mismatch: {email_address}"
    assert len(jwt_token) > 20, f"JWT too short: {jwt_token}"


def test_poll_inbox():
    """Poll inbox with JWT — must return a valid JSON results array."""
    from services.email_service import create_temp_email

    email_address, jwt_token = create_temp_email()
    assert email_address is not None, "Failed to create email for inbox test"

    headers = {"Authorization": f"Bearer {jwt_token}"}
    resp = requests.get(
        f"{EMAIL_WORKER_URL}/api/mails",
        headers=headers,
        params={"limit": 20, "offset": 0},
        timeout=15,
    )
    assert resp.status_code == 200, f"Inbox poll failed: {resp.status_code}"

    data = resp.json()
    assert "results" in data, f"No 'results' key in response: {data}"
    assert isinstance(data["results"], list), f"results is not a list: {type(data['results'])}"


def test_extract_code_from_text():
    """Code extraction regex must find 6-digit codes in sample text."""
    from helpers.utils import extract_verification_code

    cases = [
        ("Your verification code is 123456", "123456"),
        ("Code: 987654", "987654"),
        ("VERIFICATION CODE 555123", "555123"),
    ]
    for text, expected in cases:
        result = extract_verification_code(text)
        assert result == expected, f"Failed to extract from '{text}': got {result}, expected {expected}"


if __name__ == "__main__":
    tests = [
        ("Worker reachable", test_worker_reachable),
        ("Create temp email", test_create_temp_email),
        ("Poll inbox", test_poll_inbox),
        ("Extract code from text", test_extract_code_from_text),
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
    sys.exit(0 if failed == 0 else 1)