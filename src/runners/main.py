import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright
from faker import Faker
import random
import time
import json
import os
from datetime import datetime
from config import HEADLESS, SLOW_MO
from services.email_service import create_temp_email, wait_for_verification_email

fake = Faker("en_US")


def generate_strong_password():
    import string

    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(random.choices(chars, k=16))
    password = (
        random.choice(string.ascii_uppercase)
        + random.choice(string.ascii_lowercase)
        + random.choice(string.digits)
        + random.choice("!@#$%^&*")
        + password[4:]
    )
    return password


def save_account(email, password, name, jwt_token=""):
    account_info = {
        "email": email,
        "password": password,
        "name": name,
        "jwt_token": jwt_token,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "registered",
    }
    file_path = "accounts.jsonl"
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(account_info, ensure_ascii=False) + "\n")
        print(f"Account saved: {email}")
    except Exception as e:
        print(f"Failed to save account: {e}")


def human_delay(min_sec=0.5, max_sec=2.0):
    if random.random() < 0.15:
        time.sleep(random.uniform(2.5, 5.0))
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(page, selector, text):
    for char in text:
        page.locator(selector).press(char)
        delay = random.uniform(0.04, 0.15)
        if random.random() < 0.05:
            delay += random.uniform(0.2, 0.5)
        time.sleep(delay)


def human_click(page, selector):
    box = page.locator(selector).bounding_box()
    if box:
        x = box["x"] + box["width"] / 2 + random.randint(-5, 5)
        y = box["y"] + box["height"] / 2 + random.randint(-5, 5)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.1, 0.4))
        page.mouse.click(x, y)
    else:
        page.locator(selector).click()


def run(fixed_account=None):
    import os
    from config import REGION_CURRENT, DEVICE_TYPE, REGION_PROFILES
    from helpers.utils import (
        get_user_agent_for_region,
        get_locale_for_region,
        get_timezone_for_region,
        get_accept_language_for_region,
        is_mobile,
    )

    detected_region = os.environ.get("AUTO_REGION", REGION_CURRENT)

    device_emoji = "📱" if is_mobile() else "💻"
    print(f"\n{device_emoji} === Current Environment ===")
    print(f"Region: {detected_region.upper()}")
    print(f"Device: {DEVICE_TYPE.upper()}")
    print(f"Locale: {get_locale_for_region(detected_region)}")
    print(f"Timezone: {get_timezone_for_region(detected_region)}")
    print("=" * 50)

    user_agent = get_user_agent_for_region(detected_region)
    print(f"User-Agent: {user_agent[:80]}...")

    if fixed_account:
        email_address = fixed_account["email"]
        jwt_token = "OUTLOOK_API"
        print(f"Using fixed Outlook email: {email_address}")
    else:
        print("Creating temp email...")
        email_address, jwt_token = create_temp_email()

    if not email_address:
        print("Failed to create email, exiting")
        return

    common_resolutions = ["1920,1080", "1366,768", "1536,864", "1440,900", "1280,720"]
    viewport_w, viewport_h = map(int, random.choice(common_resolutions).split(","))

    playwright = None
    browser = None
    page = None

    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=HEADLESS,
            slow_mo=SLOW_MO,
            args=[
                f"--window-size={viewport_w},{viewport_h}",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": viewport_w, "height": viewport_h},
            locale=get_locale_for_region(detected_region),
            timezone_id=get_timezone_for_region(detected_region),
        )

        page = context.new_page()

        print("\nOpening AWS Builder page...")
        page.goto("https://builder.aws.com/start", wait_until="domcontentloaded")
        human_delay(2, 3)
        print(f"Page title: {page.title()}")

        try:
            cookie_btn = page.locator("button:has-text('Accept')")
            if cookie_btn.is_visible(timeout=3000):
                cookie_btn.click()
                print("Cookie popup dismissed")
                human_delay(2, 3)
        except:
            print("No cookie popup or already dismissed")

        page.screenshot(path="screenshot.png")
        print("Screenshot saved (landing page)")

        print("Clicking 'Sign up with Builder ID'...")
        signup_btn = page.locator("button:has-text('Sign up with Builder ID')")
        signup_btn.wait_for(state="visible", timeout=15000)
        signup_btn.click()
        human_delay(3, 5)
        print(f"After signup click - URL: {page.url}")
        page.screenshot(path="screenshot.png")
        print("Screenshot saved (signup page)")

        print(f"Filling email: {email_address}")
        email_input = page.locator('input[type="email"]').first
        try:
            email_input.wait_for(state="visible", timeout=15000)
        except:
            email_input = page.locator('input[placeholder*="@"]').first
            email_input.wait_for(state="visible", timeout=5000)
        email_input.click()
        human_delay(0.3, 0.8)
        email_input.fill(email_address)
        human_delay(0.5, 1)

        page.screenshot(path="screenshot.png")

        print("Clicking Continue...")
        human_delay(1, 2)
        continue_btn = page.locator('[data-testid="test-primary-button"]')
        continue_btn.wait_for(state="visible", timeout=10000)
        continue_btn.click()

        human_delay(3, 5)
        print(f"Current URL: {page.url}")
        page.screenshot(path="screenshot.png")

        random_name = fake.name()
        print(f"Filling name: {random_name}")

        for name_attempt in range(3):
            try:
                name_input = page.locator('input[type="text"]').first
                name_input.wait_for(state="visible", timeout=10000)
                name_input.click()
                human_delay(0.3, 0.5)
                name_input.fill("")
                human_delay(0.2, 0.4)
                name_input.fill(random_name)
                human_delay(0.5, 1)

                actual = name_input.input_value()
                if actual and len(actual) > 0:
                    print(f"  Input verified: '{actual}'")
                    break
                else:
                    print(f"  Input verification failed, retry...")
            except Exception as e:
                print(f"  Name input retry {name_attempt + 1}/3: {e}")
                human_delay(1, 2)

        page.screenshot(path="screenshot.png")

        print("Clicking Continue on name page...")
        human_delay(1, 2)

        for attempt in range(3):
            for sel in [
                "button:has-text('Continue')",
                "button:has-text('继续')",
                'button[type="submit"]',
                '[data-testid="test-primary-button"]',
            ]:
                btn = page.locator(sel)
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"  Clicked: {sel}")
                    break

            human_delay(5, 8)
            if "verification" in page.url.lower() or "signup" in page.url.lower():
                print(f"  Advanced to {page.url[:80]}")
                break
            if attempt < 2:
                print(f"  Retrying ({attempt + 2}/3)...")

        page.screenshot(path="screenshot.png")

        print("Waiting for verification email...")
        human_delay(3, 5)

        try:
            if fixed_account:
                from services.outlook_service import get_verification_code_from_outlook

                verification_code = get_verification_code_from_outlook(fixed_account)
            else:
                from services.email_service import wait_for_verification_email

                verification_code = wait_for_verification_email(jwt_token)
        except Exception as e:
            print(f"Error getting verification code: {e}")
            verification_code = None

        if verification_code:
            print(f"Got verification code: {verification_code}")

            try:
                print("Looking for verification code input...")
                human_delay(4, 6)

                code_input = page.locator(
                    'input[placeholder*="digit"], input[type="text"]'
                ).first
                code_input.wait_for(state="visible", timeout=15000)
                human_delay(1, 2)
                code_input.click()
                human_delay(0.5, 1)
                code_input.fill(verification_code)
                print("Code filled")

                human_delay(1.5, 2.5)

                for sel in [
                    "button:has-text('Verify')",
                    "button:has-text('Continue')",
                    "button:has-text('继续')",
                    'button[type="submit"]',
                ]:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print(f"Clicked: {sel}")
                        break

                human_delay(5, 8)

                if "verify-otp" in page.url.lower():
                    print("  Still on OTP page - code may not be accepted, retrying...")
                    human_delay(3, 5)
                    page.screenshot(path="screenshot_otp_retry.png")
                    for sel in [
                        "button:has-text('Continue')",
                        "button:has-text('继续')",
                        'button[type="submit"]',
                    ]:
                        btn = page.locator(sel)
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            human_delay(5, 8)
                            break

                human_delay(5, 8)

            except Exception as e:
                print(f"Failed to fill verification code: {e}")
        else:
            print("Failed to get verification code")

        print("Setting up password...")
        try:
            page.wait_for_selector('input[type="password"]', timeout=30000)
        except:
            page.screenshot(path="screenshot_pre_password.png")
            print(f"No password inputs found, URL: {page.url}")
            save_account(email_address, "NO_PASSWORD_YET", random_name, jwt_token)
            print("Saved account without password - may need manual completion")
            if page:
                page.close()
            return

        page.screenshot(path="screenshot.png")
        print(f"Current URL: {page.url}")

        password = generate_strong_password()
        print(f"Generated password: {password}")

        try:
            password_inputs = page.locator('input[type="password"]')
            count = password_inputs.count()
            print(f"Found {count} password inputs")

            if count >= 1:
                human_delay(0.5, 1)
                password_inputs.nth(0).click()
                password_inputs.nth(0).fill(password)
                print("Filled primary password")

                if count >= 2:
                    human_delay(0.5, 1)
                    password_inputs.nth(1).click()
                    password_inputs.nth(1).fill(password)
                    print("Filled confirm password")
                else:
                    for sel in [
                        'input[name="confirmPassword"]',
                        'input[placeholder="Confirm password"]',
                        'input[placeholder="Re-enter password"]',
                        'input[id*="confirm"]',
                    ]:
                        confirm = page.locator(sel)
                        if confirm.is_visible(timeout=2000):
                            human_delay(0.5, 1)
                            confirm.click()
                            confirm.fill(password)
                            print("Filled confirm password (alt selector)")
                            break

                page.screenshot(path="screenshot.png")

                human_delay(1, 2)
                print("Clicking Create Account button...")

                for sel in [
                    "button:has-text('Create AWS Builder ID')",
                    "button:has-text('Continue')",
                    'button[type="submit"]',
                ]:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        break
            else:
                print(
                    "No password inputs found, may already be logged in or different flow"
                )

        except Exception as e:
            print(f"Password setup error: {e}")

        human_delay(5, 8)
        print(f"Final page title: {page.title()}")
        print(f"Final URL: {page.url}")
        page.screenshot(path="final_success.png")

        save_account(email_address, password, random_name, jwt_token)
        print("\nAccount flow completed, saved to accounts.jsonl")

    except Exception as e:
        print(f"Error during process: {e}")
        try:
            if page:
                page.screenshot(path="error_screenshot.png")
            if "email_address" in locals() and "password" in locals():
                save_account(
                    email_address,
                    password,
                    locals().get("random_name", "Unknown"),
                    locals().get("jwt_token", ""),
                )
                print("Saved partial account info")
        except:
            pass

    finally:
        try:
            if page:
                page.close()
        except:
            pass
        try:
            if browser:
                browser.close()
        except:
            pass
        try:
            if playwright:
                playwright.stop()
        except:
            pass


if __name__ == "__main__":
    run()
