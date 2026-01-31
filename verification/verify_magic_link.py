import time
import re
import os
from playwright.sync_api import sync_playwright, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Go to Login
        print("Navigating to login...")
        page.goto("http://localhost:5173/login")
        expect(page.get_by_role("heading", name="Login")).to_be_visible()

        # 2. Submit Email
        print("Submitting email...")
        page.get_by_label("Email").fill("test@example.com")
        page.get_by_role("button", name="Send Magic Link").click()

        # 3. Expect Success Message
        print("Waiting for success message...")
        expect(page.get_by_text("Check your inbox!")).to_be_visible()
        page.screenshot(path="verification/magic_link_sent.png")

        # 4. Extract Token from Log
        print("Extracting token from logs...")
        time.sleep(2) # Give it a moment to write
        token = None
        if os.path.exists("server_output.txt"):
            with open("server_output.txt", "r") as f:
                for line in f:
                    if "Magic Link Generated" in line and "test@example.com" in line:
                        match = re.search(r'token=([a-f0-9-]+)', line)
                        if match:
                            token = match.group(1)

        if not token:
            print("Token not found in logs!")
            exit(1)

        print(f"Found token: {token}")

        # 5. Consume Token
        # Access via frontend proxy to ensure cookie path matches frontend domain if relevant (though path=/ usually works)
        # and to verify proxy behavior.
        consume_url_proxied = f"http://localhost:5173/api/auth/login/consume?token={token}"
        print(f"Consuming token via {consume_url_proxied}...")

        page.goto(consume_url_proxied)

        # 6. Verify Auth
        # Should redirect to home and show Logged In status
        print("Verifying authentication...")
        expect(page).to_have_url("http://localhost:5173/")

        # Check for "WEBER" badge (since we set role: weber)
        # Note: AuthStatus component renders role in uppercase
        expect(page.get_by_text("WEBER")).to_be_visible()
        page.screenshot(path="verification/magic_link_success.png")

        print("Success!")
        browser.close()

if __name__ == "__main__":
    run()
