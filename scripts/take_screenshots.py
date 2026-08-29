#!/usr/bin/env python3
"""Take screenshots of all KMS Starfarm pages for user guide documentation."""

import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "images")

# Pages to capture: (filename, url_path, description, wait_time_seconds)
PAGES = [
    ("01_login.png", "/auth/login", "Login page", 2),
    ("02_dashboard_overview.png", "/", "Dashboard overview", 4),
    ("03_mango_chain.png", "/?tab=mango", "Mango value chain tab", 3),
    ("04_cross_chain.png", "/?tab=cross-chain", "Cross-chain comparison", 3),
    ("05_documents.png", "/documents", "Document management", 3),
    ("06_chat.png", "/chat", "Chat interface", 3),
    ("07_knowledge_config.png", "/knowledge", "Knowledge pipeline config", 3),
    ("08_kpi_review.png", "/kpi-review", "KPI review and approval", 3),
    ("09_settings.png", "/settings", "Settings page", 2),
]


def login(page):
    """Perform mock login with any credentials."""
    page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle", timeout=15000)
    time.sleep(1)

    # Fill in email and password (mock auth accepts anything)
    page.fill('input[type="email"]', "admin@kms-starfarm.org")
    page.fill('input[type="password"]', "password123")

    # Click the Sign In button
    page.click('button[type="submit"]')

    # Wait for navigation away from login page
    time.sleep(3)
    page.wait_for_load_state("networkidle", timeout=10000)

    current_url = page.url
    if "/auth/login" in current_url:
        print(f"  WARNING: Still on login page after sign-in attempt. URL: {current_url}")
        # Try clicking any visible button
        buttons = page.query_selector_all("button")
        for btn in buttons:
            text = btn.inner_text()
            if "sign" in text.lower() or "log" in text.lower():
                btn.click()
                time.sleep(3)
                break
    else:
        print(f"  Logged in successfully. Now at: {current_url}")


def take_screenshots():
    """Main function to capture all page screenshots."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,  # Retina quality
        )
        page = context.new_page()

        # Step 1: Capture login page (before auth)
        print("Step 1: Capturing login page...")
        page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle", timeout=15000)
        time.sleep(2)
        page.screenshot(
            path=os.path.join(OUTPUT_DIR, "01_login.png"), full_page=False
        )
        print("  -> 01_login.png saved")

        # Step 2: Log in
        print("Step 2: Logging in...")
        login(page)

        # Step 3: Capture each authenticated page
        for i, (filename, url_path, description, wait_time) in enumerate(PAGES[1:], start=2):
            print(f"Step {i}: Capturing {description}...")

            full_url = f"{BASE_URL}{url_path}"
            try:
                page.goto(full_url, wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(full_url, wait_until="load", timeout=15000)

            time.sleep(wait_time)

            filepath = os.path.join(OUTPUT_DIR, filename)
            page.screenshot(path=filepath, full_page=False)
            print(f"  -> {filename} saved")

        # Also capture a full-page dashboard screenshot
        print("Step 10: Capturing full-page dashboard...")
        page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
        time.sleep(4)
        page.screenshot(
            path=os.path.join(OUTPUT_DIR, "02b_dashboard_fullpage.png"),
            full_page=True,
        )
        print("  -> 02b_dashboard_fullpage.png saved")

        browser.close()
        print(f"\nAll screenshots saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    take_screenshots()
