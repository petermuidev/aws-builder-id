"""
邮箱服务模块
适配 generator.email (替代 cloudflare_temp_email)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import random
import re
import string
import time
from typing import Optional

import requests as http_requests
from lxml import html as lxml_html

from config import (
    EMAIL_DOMAIN,
    EMAIL_PREFIX_LENGTH,
    EMAIL_WAIT_TIMEOUT,
    EMAIL_POLL_INTERVAL,
    HTTP_TIMEOUT,
)
from helpers.utils import http_session, get_user_agent, extract_verification_code

GENERATOR_EMAIL_URL = "https://generator.email"

TEMP_EMAIL_DOMAINS = [
    "fundproceed.com",
    "careandvital.com",
    "btcmod.com",
    "getcode1.com",
    "speeddataanalytics.com",
    "sedekah-mudah.com",
    "capcutpro.click",
]

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = http_requests.Session()
        _session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
    return _session


def create_temp_email():
    """
    创建临时邮箱 (使用 generator.email)
    返回: (邮箱地址, token_dict_json)，失败返回 (None, None)
    """
    print("正在创建临时邮箱...")

    prefix = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=EMAIL_PREFIX_LENGTH)
    )

    if EMAIL_DOMAIN in ("your-domain.com", ""):
        domain = random.choice(TEMP_EMAIL_DOMAINS)
    else:
        domain = EMAIL_DOMAIN

    email_address = f"{prefix}@{domain}"
    token = json.dumps({"username": prefix, "domain": domain})

    print(f"邮箱创建成功: {email_address}")
    return email_address, token


def _fetch_mailbox_page(username: str, domain: str) -> Optional[str]:
    sess = _get_session()
    url = f"{GENERATOR_EMAIL_URL}/{domain}/{username}"
    for attempt in range(3):
        try:
            resp = sess.get(url, timeout=15, headers={"Connection": "close"})
            if resp.status_code == 200:
                return resp.text
        except Exception:
            time.sleep(2)
    return None


def _parse_email_body(email_url: str) -> str:
    sess = _get_session()
    try:
        resp = sess.get(email_url, timeout=15)
        if resp.status_code == 200:
            tree = lxml_html.fromstring(resp.text)
            body_parts = tree.xpath(
                '//div[contains(@class, "e7m")]//text() | //td//text() | //p//text()'
            )
            return " ".join(t.strip() for t in body_parts if t.strip())
    except Exception as e:
        print(f"  读取邮件内容错误: {e}")
    return ""


def _extract_aws_code(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in [
        r"\b(\d{6})\b",
        r"code[:\s]+(\d{6})",
        r"Code[:\s]+(\d{6})",
        r"verification[:\s]+(\d{6})",
        r"VERIFICATION\s+CODE[:\s]+(\d{6})",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def wait_for_verification_email(token_str: str, timeout: int = None):
    """
    等待并提取验证码 (从 generator.email 页面轮询)
    返回: 验证码字符串，未找到返回 None
    """
    if timeout is None:
        timeout = EMAIL_WAIT_TIMEOUT

    try:
        token_data = json.loads(token_str)
        username = token_data["username"]
        domain = token_data["domain"]
    except (json.JSONDecodeError, KeyError):
        print("  token 格式无效，无法读取邮箱")
        return None

    print(f"正在等待验证邮件（最长 {timeout} 秒）...")
    start_time = time.time()
    seen_links = set()

    while time.time() - start_time < timeout:
        page_html = _fetch_mailbox_page(username, domain)
        if page_html is None:
            time.sleep(EMAIL_POLL_INTERVAL)
            continue

        tree = lxml_html.fromstring(page_html)

        links = tree.xpath('//a[contains(@id, "iddelet")]')
        for link in links:
            href = link.get("href", "")
            link_text = link.text_content().strip()

            if href in seen_links:
                continue
            seen_links.add(href)

            combined = (link_text + " " + href).lower()
            if any(
                kw in combined
                for kw in ("amazon", "aws", "builder", "verification", "verify", "code")
            ):
                print(f"\n收到可能的验证邮件: {link_text[:80]}")

                if href.startswith("http"):
                    email_url = href
                else:
                    email_url = f"{GENERATOR_EMAIL_URL}{href}"

                body_text = _parse_email_body(email_url)
                code = _extract_aws_code(link_text)
                if not code and body_text:
                    code = _extract_aws_code(body_text)

                if code:
                    print(f"   验证码: {code}")
                    return code

        full_text = " ".join(t.strip() for t in tree.xpath("//text()") if t.strip())
        code = _extract_aws_code(full_text)
        if code:
            print(f"\n   在邮箱主页找到验证码: {code}")
            return code

        elapsed = int(time.time() - start_time)
        print(f"  等待中... ({elapsed}秒)", end="\r")
        time.sleep(EMAIL_POLL_INTERVAL)

    print("\n等待验证邮件超时")
    return None
