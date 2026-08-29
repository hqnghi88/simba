#!/usr/bin/env python3
"""Capture additional screenshots for the expanded KMS User Guide."""

import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "images")


def login(page):
    """Inject mock auth tokens directly."""
    page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle", timeout=15000)
    page.evaluate(
        """() => {
            localStorage.setItem('accessToken', 'mock-access-token');
            localStorage.setItem('refreshToken', 'mock-refresh-token');
            localStorage.setItem('userId', 'mock-user-id');
            localStorage.setItem('userEmail', 'admin@kms-starfarm.org');
        }"""
    )


def capture():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900}, device_scale_factor=2
        )
        page = context.new_page()
        login(page)

        def shot(name, description):
            page.screenshot(path=os.path.join(OUTPUT_DIR, name), full_page=False)
            print(f"  -> {name} ({description})")

        # ── 1. DOCUMENT MANAGEMENT: Upload dialog ─────────────────────
        print("[1/12] Capturing Documents → Upload dialog...")
        page.goto(f"{BASE_URL}/documents", wait_until="networkidle", timeout=15000)
        time.sleep(3)
        page.click("button:has-text('Upload')")
        time.sleep(2)
        shot("10_upload_dialog.png", "Upload dialog - File tab")

        # Folder Upload tab
        try:
            page.click('button:has-text("Folder Upload")')
            time.sleep(1)
            shot("10b_upload_folder_tab.png", "Upload dialog - Folder tab")
        except Exception as e:
            print(f"  WARNING: Folder Upload tab failed: {e}")

        # Dataverse tab
        try:
            page.click('button:has-text("Dataverse")')
            time.sleep(1)
            shot("10c_upload_dataverse_tab.png", "Upload dialog - Dataverse tab")
        except Exception as e:
            print(f"  WARNING: Dataverse tab failed: {e}")
        # Cancel the dialog
        try:
            page.click("button:has-text('Cancel')")
            time.sleep(1)
        except Exception:
            page.keyboard.press("Escape")
            time.sleep(1)

        # ── 2. DOCUMENT MANAGEMENT: Create folder dialog ──────────────
        print("[2/12] Capturing Create Folder dialog...")
        try:
            page.click("button:has-text('New Folder')")
            time.sleep(1)
            shot("10d_new_folder_dialog.png", "Create New Folder dialog")
            page.click("button:has-text('Cancel')")
        except Exception as e:
            print(f"  WARNING: New Folder dialog failed: {e}")
        time.sleep(1)

        # ── 3. CHAT: Ask a real question ──────────────────────────────
        print("[3/12] Capturing Chat with real question...")
        page.goto(f"{BASE_URL}/chat", wait_until="networkidle", timeout=15000)
        time.sleep(2)
        page.fill('input[placeholder="Poser une question"]', "What is the Mango revenue for cooperative farmers?")
        page.press('input[placeholder="Poser une question"]', "Enter")
        print("  Waiting for thinking animation...")
        # Poll for the Thinking indicator briefly
        for _ in range(20):
            try:
                page.wait_for_selector("text=Thinking", timeout=1500)
                shot("10e_chat_thinking.png", "Chat - thinking animation")
                break
            except Exception:
                time.sleep(0.5)
        print("  Waiting for answer to stream...")
        try:
            page.wait_for_selector('text=Sources (', timeout=60000)
            time.sleep(2)
        except Exception:
            print("  WARNING: No Sources button appeared within 60s")
        time.sleep(3)
        shot("10f_chat_answer.png", "Chat - complete answer")

        # Sources panel
        try:
            page.click('button:has-text("Sources (")')
            time.sleep(2)
            shot("10g_chat_sources.png", "Chat - Sources panel open")
        except Exception:
            print("  WARNING: Sources button not found - skipping")

        # ── 4. DOCUMENT PREVIEW MODAL ─────────────────────────────────
        print("[4/12] Capturing Document preview modal...")
        page.goto(f"{BASE_URL}/documents", wait_until="networkidle", timeout=15000)
        time.sleep(3)
        try:
            # Find the first row with an eye icon (View)
            page.query_selector("button[aria-label*='View' i], svg[aria-hidden]")
            # Click the eye action - look for a button with a view/eye
            view_btn = page.query_selector("button:has(svg.lucide-eye), button[title='View']")
            if not view_btn:
                # Try clicking first row action - might be a hover-trigger
                first_row = page.query_selector("table tbody tr")
                if first_row:
                    first_row.hover()
                    time.sleep(0.5)
            time.sleep(1)
            # Look for buttons in the row actions column
            for btn in page.query_selector_all("table tbody tr:first-child button"):
                cls = btn.get_attribute("class") or ""
                title = (btn.get_attribute("title") or "").lower()
                aria = (btn.get_attribute("aria-label") or "").lower()
                if "eye" in cls or "view" in title or "view" in aria or "Preview" in cls or "preview" in aria:
                    btn.click()
                    time.sleep(2)
                    break
            shot("10h_preview_modal.png", "Document Preview modal (chunks)")
            page.keyboard.press("Escape")
        except Exception as e:
            print(f"  WARNING: Could not open preview modal: {e}")

        # ── 5. DASHBOARD: recapture for consistency ───────────────────
        print("[5/12] Capturing Dashboard...")
        page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
        time.sleep(4)
        shot("11_dashboard.png", "Dashboard overview")

        # ── 6. KNOWLEDGE CONFIG: expanded accordion ───────────────────
        print("[6/12] Capturing Knowledge config with expanded section...")
        page.goto(f"{BASE_URL}/knowledge", wait_until="networkidle", timeout=15000)
        time.sleep(2)
        # Expand all accordion sections
        chevrons = page.query_selector_all("button[aria-expanded='false']")
        for c in chevrons:
            try:
                c.click()
            except Exception:
                pass
        time.sleep(1)
        shot("12_knowledge_full.png", "Knowledge config - all expanded")
        shot("12b_knowledge_retrieval.png", "Knowledge config - retrieval section")

        # ── 7. KPI REVIEW: interactive state ──────────────────────────
        print("[7/12] Capturing KPI Review page...")
        page.goto(f"{BASE_URL}/kpi-review", wait_until="networkidle", timeout=15000)
        time.sleep(5)
        shot("13_kpi_review.png", "KPI Review page")

        # ── 8. SETTINGS: recapture for quality ────────────────────────
        print("[8/12] Capturing Settings pages...")
        for sub, name in [
            ("", "14_settings_general"),
            ("organizations", "14b_settings_orgs"),
            ("members", "14c_settings_members"),
            ("roles", "14d_settings_roles"),
            ("api-keys", "14e_settings_apikeys"),
        ]:
            url = f"{BASE_URL}/settings/{sub}" if sub else f"{BASE_URL}/settings"
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(2)
            # Check for error state
            content = page.content()
            if "Backend API calls are currently disabled" in content:
                print(f"  WARNING: {name} shows disabled error - skipping")
            else:
                shot(f"{name}.png", f"Settings - {sub or 'general'}")

        # ── 9. API DOCS (Swagger) ─────────────────────────────────────
        print("[9/12] Capturing API docs...")
        page.goto("http://localhost:8081/docs", wait_until="networkidle", timeout=15000)
        time.sleep(3)
        shot("15_api_docs.png", "API Docs - Swagger UI")

        # ── 10. PDF PREVIEW ───────────────────────────────────────────
        print("[10/12] Capturing docs page with breadcrumb/folder...")
        page.goto(f"{BASE_URL}/documents", wait_until="networkidle", timeout=15000)
        time.sleep(3)
        shot("16_documents_full.png", "Documents full view")

        # ── 11. Login recapture ───────────────────────────────────────
        print("[11/12] Recapturing Login page...")
        page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle", timeout=15000)
        time.sleep(2)
        shot("17_login.png", "Login page")

        # ── 12. Sign-up page ──────────────────────────────────────────
        print("[12/12] Capturing Sign up page...")
        page.click("text=Sign up")
        time.sleep(2)
        shot("17b_signup.png", "Sign up page")
        page.keyboard.press("Escape")

        browser.close()
        print("\nAll additional screenshots saved.")


if __name__ == "__main__":
    capture()