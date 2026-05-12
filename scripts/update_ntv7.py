import os
import re
from playwright.sync_api import sync_playwright

EMAIL = os.getenv("TONTON_EMAIL")
PASSWORD = os.getenv("TONTON_PASSWORD")

TARGET = "https://watch.tonton.com.my/live/ntv7"

found = None

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled"
        ]
    )

    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    page = context.new_page()

    # =====================================================
    # Capture ALL network responses
    # =====================================================
    def handle_response(response):
        global found

        try:
            url = response.url

            # Detect m3u8 stream
            if ".m3u8" in url and "ntv7" in url:

                # Make sure full authenticated URL
                if "bpkio_sessionid" in url:

                    found = url

                    print("\n================================")
                    print("FOUND STREAM URL")
                    print(url)
                    print("================================\n")

        except Exception:
            pass

    page.on("response", handle_response)

    # =====================================================
    # Open homepage
    # =====================================================
    print("Opening Tonton homepage...")

    page.goto(
        "https://www.tonton.com.my",
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(8000)

    # =====================================================
    # Open login popup
    # =====================================================
    print("Waiting Sign In button...")

    page.wait_for_selector('text=Sign In', timeout=30000)

    print("Opening login popup...")

    with page.expect_popup() as popup_info:
        page.click('text=Sign In')

    popup = popup_info.value

    popup.wait_for_load_state("networkidle")

    print("Popup loaded")

    popup.wait_for_timeout(5000)

    # =====================================================
    # Fill credentials
    # =====================================================
    print("Entering credentials...")

    popup.wait_for_selector(
        'input[type="text"]',
        timeout=30000
    )

    popup.fill(
        'input[type="text"]',
        EMAIL
    )

    popup.fill(
        'input[type="password"]',
        PASSWORD
    )

    # =====================================================
    # Human-like mouse move
    # =====================================================
    print("Submitting login...")

    submit_btn = popup.locator('#submitBtn')

    box = submit_btn.bounding_box()

    if box:
        popup.mouse.move(
            box["x"] + box["width"] / 2,
            box["y"] + box["height"] / 2,
            steps=20
        )

        popup.wait_for_timeout(500)

    submit_btn.click()

    # =====================================================
    # WAIT AFTER LOGIN (ADVERTISEMENT)
    # =====================================================
    print("Waiting advertisement after login...")

    page.wait_for_timeout(3000)

    # =====================================================
    # Close popup if still exists
    # =====================================================
    try:
        popup.close()
    except:
        pass

    # =====================================================
    # Navigate to NTV7 live page
    # =====================================================
    print("Opening NTV7 page...")

    page.goto(
        TARGET,
        wait_until="domcontentloaded",
        timeout=120000
    )

    # =====================================================
    # Wait for player & network requests
    # =====================================================
    print("Waiting stream network requests...")

    # Allow video player to initialize
    page.wait_for_timeout(20000)

    # =====================================================
    # Fallback: scrape performance entries
    # =====================================================
    if not found:

        print("Trying fallback performance scrape...")

        urls = page.evaluate("""
        () => {
            return performance
                .getEntriesByType('resource')
                .map(r => r.name)
        }
        """)

        for url in urls:
            if ".m3u8" in url and "ntv7" in url:

                if "bpkio_sessionid" in url:
                    found = url
                    break

    browser.close()

# =====================================================
# Validate result
# =====================================================
if not found:
    raise Exception("No stream URL found")

# =====================================================
# Clean duplicated escaped URLs if needed
# =====================================================
found = re.sub(r'\\\\u0026', '&', found)

# =====================================================
# Generate M3U
# =====================================================
m3u = f"""#EXTM3U
#EXTINF:-1 tvg-id="NTV7.my" tvg-name="NTV7" group-title="Malaysia",NTV7
{found}
"""

with open(
    "ntv7.m3u",
    "w",
    encoding="utf-8"
) as f:
    f.write(m3u)

print("\n================================")
print("M3U UPDATED SUCCESSFULLY")
print(found)
print("================================\n")