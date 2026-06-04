"""
Email service module — uses cloudflare_temp_email Worker API
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import email as email_lib
import json
import random
import re
import string
import time
from email import policy
from typing import Optional

import requests as http_requests

from config import (
    EMAIL_WORKER_URL,
    EMAIL_DOMAIN,
    EMAIL_PREFIX_LENGTH,
    EMAIL_WAIT_TIMEOUT,
    EMAIL_POLL_INTERVAL,
)


def create_temp_email():
    """
    Create a temp email address via cloudflare_temp_email Worker.
    Returns: (email_address, jwt_token), or (None, None) on failure.
    """
    print("Creating temp email via Worker API...")

    prefix = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=EMAIL_PREFIX_LENGTH)
    )
    name = f"tmp{prefix}"

    try:
        resp = http_requests.post(
            f"{EMAIL_WORKER_URL}/api/new_address",
            json={"name": name, "domain": EMAIL_DOMAIN},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  Failed to create address: {resp.status_code} {resp.text}")
            return None, None

        data = resp.json()
        jwt_token = data["jwt"]
        email_address = data["address"]
        print(f"  Email created: {email_address}")
        return email_address, jwt_token

    except Exception as e:
        print(f"  Error creating email: {e}")
        return None, None


def _parse_raw_email(raw: str) -> dict:
    """Parse raw MIME content into {subject, body, sender}."""
    result = {"subject": "", "body": "", "sender": ""}
    if not raw:
        return result
    try:
        msg = email_lib.message_from_string(raw, policy=policy.default)
        result["subject"] = msg.get("Subject", "")
        result["sender"] = msg.get("From", "")
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        result["body"] = payload.decode("utf-8", errors="ignore")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                result["body"] = payload.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Parse error: {e}")
    return result


def _extract_aws_code(text: str) -> Optional[str]:
    if not text:
        return None
    # Priority patterns for AWS verification
    for pattern in [
        r"verification\s+code[:\s]+(\d{6})",
        r"VERIFICATION\s+CODE[:\s]+(\d{6})",
        r"code[:\s]+(\d{6})",
        r"Code[:\s]+(\d{6})",
        r"\b(\d{6})\b",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def wait_for_verification_email(jwt_token: str, timeout: int = None):
    """
    Poll Worker API for incoming emails and extract AWS verification code.
    The API returns {id, message_id, source, address, raw, ...} —
    subject and body are inside raw MIME content, not separate fields.
    Returns: verification code string, or None on timeout.
    """
    if timeout is None:
        timeout = EMAIL_WAIT_TIMEOUT

    print(f"Waiting for verification email (max {timeout}s)...")

    headers = {"Authorization": f"Bearer {jwt_token}"}
    seen_ids = set()
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            resp = http_requests.get(
                f"{EMAIL_WORKER_URL}/api/mails",
                headers=headers,
                params={"limit": 20, "offset": 0},
                timeout=15,
            )
            if resp.status_code != 200:
                time.sleep(EMAIL_POLL_INTERVAL)
                continue

            data = resp.json()
            results = data.get("results", [])

            for mail in results:
                mail_id = mail.get("id")
                if mail_id in seen_ids:
                    continue
                seen_ids.add(mail_id)

                # Parse raw MIME for subject, body, sender
                raw = mail.get("raw", "")
                parsed = _parse_raw_email(raw)
                subject = parsed["subject"]
                body = parsed["body"]
                sender = parsed["sender"].lower()

                # Also check direct fields as fallback
                if not subject:
                    subject = mail.get("subject", "")
                if not sender:
                    sender = str(mail.get("from", "") or mail.get("source", "")).lower()

                # Check if this is an AWS verification email
                combined = (subject + " " + sender).lower()
                if any(
                    kw in combined
                    for kw in ("amazon", "aws", "builder", "verification", "verify", "signin")
                ):
                    print(f"\n  Found verification email: {subject[:80]}")

                    # Try subject first
                    code = _extract_aws_code(subject)
                    if code:
                        print(f"  Verification code (from subject): {code}")
                        return code

                    # Then from body (parsed from raw MIME)
                    if body:
                        code = _extract_aws_code(body)
                        if code:
                            print(f"  Verification code (from body): {code}")
                            return code

                    # Fetch individual mail detail if still no code
                    mail_resp = http_requests.get(
                        f"{EMAIL_WORKER_URL}/api/mail/{mail_id}",
                        headers=headers,
                        timeout=15,
                    )
                    if mail_resp.status_code == 200:
                        mail_data = mail_resp.json()
                        detail_raw = mail_data.get("raw", "")
                        if detail_raw:
                            parsed_detail = _parse_raw_email(detail_raw)
                            code = _extract_aws_code(parsed_detail["subject"])
                            if code:
                                return code
                            code = _extract_aws_code(parsed_detail["body"])
                            if code:
                                return code

                        # Try other content fields
                        for field in ("text", "source", "html", "html_content", "content"):
                            content = mail_data.get(field, "")
                            if content:
                                code = _extract_aws_code(content)
                                if code:
                                    print(f"  Verification code (from {field}): {code}")
                                    return code

            # Fallback: check all raw content for any 6-digit code
            for mail in results:
                raw = mail.get("raw", "")
                if raw:
                    code = _extract_aws_code(raw)
                    if code:
                        print(f"  Verification code (fallback raw scan): {code}")
                        return code

        except Exception as e:
            print(f"  Poll error: {e}")

        elapsed = int(time.time() - start_time)
        print(f"  Waiting... ({elapsed}s)", end="\r")
        time.sleep(EMAIL_POLL_INTERVAL)

    print("\n  Verification email timeout")
    return None