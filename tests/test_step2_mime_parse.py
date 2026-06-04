"""
Step 2 verification: Email MIME parsing and code extraction.
Only passes with real parsing — uses actual AWS email format.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.email_service import _parse_raw_email, _extract_aws_code


# Sample raw MIME from a real AWS Builder ID verification email
AWS_RAW_EMAIL = """\
Received: from a9-20.smtp-out.amazonses.com (54.240.9.20)
        by cloudflare-email.net (cloudflare) id XqWi97bFqiIy
        for <test@samuifreedom.online>; Thu, 04 Jun 2026 17:05:21 +0000
From: no-reply@signin.aws
To: test@samuifreedom.online
Subject: Verify your AWS Builder ID email address
MIME-Version: 1.0
Content-Type: multipart/alternative;
	boundary="----=_Part_233500_689999741.1780592721207"

------=_Part_233500_689999741.1780592721207
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 7bit

Verify your AWS Builder ID email address

Hi there,

Verification code:: 964566

This code will expire 30 minutes after it was sent.

------=_Part_233500_689999741.1780592721207--"""


def test_parse_raw_email_subject():
    """MIME parsing must extract subject from raw AWS email."""
    parsed = _parse_raw_email(AWS_RAW_EMAIL)
    assert "Verify" in parsed["subject"], f"Subject not parsed: {parsed['subject']}"
    assert "AWS Builder ID" in parsed["subject"], f"Missing 'AWS Builder ID': {parsed['subject']}"


def test_parse_raw_email_sender():
    """MIME parsing must extract sender from raw AWS email."""
    parsed = _parse_raw_email(AWS_RAW_EMAIL)
    assert "signin.aws" in parsed["sender"].lower(), f"Sender not parsed: {parsed['sender']}"


def test_parse_raw_email_body():
    """MIME parsing must extract body containing the code."""
    parsed = _parse_raw_email(AWS_RAW_EMAIL)
    assert len(parsed["body"]) > 0, "Body is empty"
    assert "964566" in parsed["body"], f"Code not found in body: {parsed['body'][:100]}"


def test_extract_code_from_body():
    """Code extraction must find 6-digit code in parsed email body."""
    parsed = _parse_raw_email(AWS_RAW_EMAIL)
    code = _extract_aws_code(parsed["body"])
    assert code == "964566", f"Expected 964566, got: {code}"


def test_extract_code_from_raw():
    """Code extraction must work directly on raw MIME content."""
    code = _extract_aws_code(AWS_RAW_EMAIL)
    assert code == "964566", f"Expected 964566 from raw, got: {code}"


def test_extract_code_double_colon():
    """AWS uses 'Verification code:: 123456' — double colon must match."""
    code = _extract_aws_code("Verification code:: 123456")
    assert code == "123456", f"Double colon format not matched: {code}"


def test_extract_code_no_false_positive():
    """No code from text without a 6-digit number."""
    code = _extract_aws_code("Hello, no code here")
    assert code is None, f"False positive: {code}"


if __name__ == "__main__":
    tests = [
        ("Parse subject from raw MIME", test_parse_raw_email_subject),
        ("Parse sender from raw MIME", test_parse_raw_email_sender),
        ("Parse body from raw MIME", test_parse_raw_email_body),
        ("Extract code from body", test_extract_code_from_body),
        ("Extract code from raw", test_extract_code_from_raw),
        ("Extract code double colon", test_extract_code_double_colon),
        ("No false positive", test_extract_code_no_false_positive),
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