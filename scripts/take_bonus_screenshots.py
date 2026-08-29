#!/usr/bin/env python3
"""Capture the Chat Thinking animation and sign-up detail for the guide."""

import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "images")


def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = context.new_page()
        page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle", timeout=15000)
        page.evaluate(
            """() => {
                localStorage.setItem('accessToken', 'mock-access-token');
                localStorage.setItem('refreshToken', 'mock-refresh-token');
                localStorage.setItem('userId', 'mock-user-id');
                localStorage.setItem('userEmail', 'admin@kms-starfarm.org');
            }"""
        )

        page.goto(f"{BASE_URL}/chat", wait_until="networkidle", timeout=15000)
        time.sleep(2)

        # Ask a distinctive question to trigger the pipeline
        page.fill('input[placeholder="Poser une question"]', "Summarise the key indicators for the Coconut value chain.")
        page.press('input[placeholder="Poser une question"]', "Enter")

        # Capture the Thinking animation as quickly as possible
        captured_thinking = False
        for _ in range(60):
            try:
                page.wait_for_selector('img[alt="Thinking animation"]', timeout=1000)
                time.sleep(0.4)  # let it render one frame
                page.screenshot(
                    path=os.path.join(OUTPUT_DIR, "10e_chat_thinking.png"),
                )
                print("  -> 10e_chat_thinking.png (Thinking animation)")
                captured_thinking = True
                break
            except Exception:
                time.sleep(0.2)

        if not captured_thinking:
            print("  WARNING: Thinking animation not detected in time")

        # Wait for answer
        try:
            page.wait_for_selector('text=Sources (', timeout=90000)
            time.sleep(3)
            page.screenshot(path=os.path.join(OUTPUT_DIR, "10f_chat_answer.png"))
            print("  -> 10f_chat_answer.png (complete answer)")
        except Exception:
            print("  WARNING: Answer did not complete")
            page.screenshot(path=os.path.join(OUTPUT_DIR, "10f_chat_answer.png"))

        browser.close()


if __name__ == "__main__":
    capture()