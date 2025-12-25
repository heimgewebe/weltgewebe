from playwright.sync_api import sync_playwright, expect
import time
import json

def verify_refined():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 412, 'height': 915})
        page = context.new_page()

        # Mock API responses
        def handle_nodes(route):
            route.fulfill(status=200, content_type="application/json", body=json.dumps([]))

        def handle_accounts(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps([
                    {
                        "id": "acc1",
                        "title": "Test Garnrolle",
                        "public_pos": {"lat": 53.560, "lon": 10.062},
                        "summary": "My Account",
                        "type": "garnrolle"
                    }
                ])
            )

        def handle_edges(route):
             route.fulfill(status=200, content_type="application/json", body=json.dumps([]))

        page.route("**/api/nodes", handle_nodes)
        page.route("**/api/accounts", handle_accounts)
        page.route("**/api/edges", handle_edges)

        try:
            print("Navigating to map...")
            page.goto("http://localhost:4173/map", wait_until="networkidle")
            page.wait_for_selector("#map", timeout=10000)
            time.sleep(2)

            # Check Map Marker
            print("Checking Map Markers...")
            marker = page.locator('.marker-account').first
            marker.wait_for(state='visible', timeout=10000)

            # Take a zoomed-in screenshot of the marker area
            # We can't easily zoom the camera in code without complex map interactions,
            # but we can verify the element screenshot
            marker.screenshot(path="verification_marker_refined.png")
            print("Marker screenshot taken: verification_marker_refined.png")

            # Full page for context
            page.screenshot(path="verification_refined_full.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="verification_refined_error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_refined()
