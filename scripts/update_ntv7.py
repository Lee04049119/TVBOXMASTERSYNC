import os
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

    # ============================================
    # Capture m3u8 requests
    # ============================================
    def handle_response(response):
        global found

        url = response.url

        if ".m3u8" in url and "ntv7" in url:
            found = url

            print("================================")
            print("FOUND STREAM URL")
            print(url)
            print("================================")

    page.on("response", handle_response)

    # ============================================
    # Open Tonton
    # ============================================
    print("Opening Tonton homepage...")

    page.goto(
        "https://www.tonton.com.my",
        wait_until="domcontentloaded",
        timeout=120000
    )

    # Wait ads / JS / cookies
    page.wait_for_timeout(8000)

    # ============================================
    # Wait Sign In button
    # ============================================
    print("Waiting for Sign In button...")

    page.wait_for_selector('text=Sign In', timeout=30000)

    print("Opening login popup...")

    # ============================================
    # Capture popup window
    # ============================================
    with page.expect_popup() as popup_info:
        page.click('text=Sign In')

    popup = popup_info.value

    # ============================================
    # Wait popup fully loaded
    # ============================================
    popup.wait_for_load_state("networkidle")

    print("Popup loaded")

    # Extra wait for RMG Services login render
    popup.wait_for_timeout(5000)

    # ============================================
    # Fill login form
    # ============================================
    print("Entering credentials...")

    popup.wait_for_selector(
        'input[type="email"]',
        timeout=30000
    )

    popup.fill(
        'input[type="email"]',
        EMAIL
    )

    popup.fill(
        'input[type="password"]',
        PASSWORD
    )

    # ============================================
    # Submit login
    # ============================================
    print("Submitting login...")

    popup.click('button[type="submit"]')

    # Wait login processing
    popup.wait_for_timeout(10000)

    # ============================================
    # Close popup if still open
    # ============================================
    try:
        popup.close()
    except:
        pass

    # ============================================
    # Open NTV7 page
    # ============================================
    print("Opening NTV7 live page...")

    page.goto(
        TARGET,
        wait_until="networkidle",
        timeout=120000
    )

    # ============================================
    # Wait stream requests
    # ============================================
    print("Waiting for m3u8 stream...")

    page.wait_for_timeout(20000)

    browser.close()

# ============================================
# Validate result
# ============================================
if not found:
    raise Exception("No stream URL found")

# ============================================
# Generate M3U
# ============================================
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

print("================================")
print("M3U UPDATED SUCCESSFULLY")
print(found)
print("================================")
