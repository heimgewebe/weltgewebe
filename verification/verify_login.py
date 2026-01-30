from playwright.sync_api import sync_playwright, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to login page
        print("Navigating to login page...")
        page.goto("http://localhost:5173/login")

        # Verify title and elements
        print("Verifying elements...")
        expect(page).to_have_title("Login")
        expect(page.get_by_role("heading", name="Login")).to_be_visible()
        expect(page.get_by_label("Account ID")).to_be_visible()
        expect(page.get_by_role("button", name="Login")).to_be_visible()

        # Take initial screenshot
        print("Taking initial screenshot...")
        page.screenshot(path="verification/login_initial.png")

        # Test error state (since backend is down)
        print("Testing error state...")
        page.get_by_label("Account ID").fill("test-user")
        page.get_by_role("button", name="Login").click()

        # Expect error message
        # The error message is "Login failed. Please check your Account ID."
        error_locator = page.get_by_text("Login failed. Please check your Account ID.")
        expect(error_locator).to_be_visible()

        # Take error screenshot
        print("Taking error screenshot...")
        page.screenshot(path="verification/login_error.png")

        browser.close()

if __name__ == "__main__":
    run()
