import os
import re
from playwright.sync_api import sync_playwright

# =====================================================
# ENVIRONMENT VARIABLES
# =====================================================
EMAIL = os.getenv("TONTON_EMAIL")
PASSWORD = os.getenv("TONTON_PASSWORD")

TARGET = "https://watch.tonton.com.my/live/ntv7"

if not EMAIL or not PASSWORD:
    raise Exception("Missing TONTON_EMAIL or TONTON_PASSWORD")

# =====================================================
# STORE FOUND URL
# =====================================================
found = {"url": None}

# =====================================================
# START PLAYWRIGHT
# =====================================================
with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu"
        ]
    )

    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    )

    page = context.new_page()

    # =====================================================
    # CAPTURE NETWORK RESPONSES
    # =====================================================
    def handle_response(response):

        try:
            url = response.url

            # Debug output
            if ".m3u8" in url:
                print("M3U8 DETECTED:", url)

            # Detect authenticated NTV7 stream
            if ".m3u8" in url and "ntv7" in url:

                if "bpkio_sessionid" in url:

                    found["url"] = url

                    print("\n================================")
                    print("FOUND STREAM URL")
                    print(url)
                    print("================================\n")

        except Exception as e:
            print("Response error:", e)

    page.on("response", handle_response)

    # =====================================================
    # OPEN HOMEPAGE
    # =====================================================
    print("Opening Tonton homepage...")

    page.goto(
        "https://www.tonton.com.my",
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(8000)

    # =====================================================
    # OPEN LOGIN POPUP
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
    # ENTER LOGIN DETAILS
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
    # HUMAN-LIKE MOUSE MOVEMENT
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
    # WAIT AFTER LOGIN
    # =====================================================
    print("Waiting after login...")

    page.wait_for_timeout(5000)

    # =====================================================
    # CLOSE POPUP
    # =====================================================
    try:
        popup.close()
    except Exception:
        pass

    # =====================================================
    # OPEN NTV7 PAGE
    # =====================================================
    print("Opening NTV7 live page...")

    page.goto(
        TARGET,
        wait_until="domcontentloaded",
        timeout=120000
    )

    # =====================================================
    # WAIT FOR STREAM REQUESTS
    # =====================================================
    print("Waiting stream network requests...")

    page.wait_for_timeout(25000)

    browser.close()

# =====================================================
# VALIDATE STREAM URL
# =====================================================
if not found["url"]:
    raise Exception("No stream URL found")

# =====================================================
# CLEAN URL
# =====================================================
found_url = re.sub(
    r'\\\\u0026',
    '&',
    found["url"]
)

# =====================================================
# GENERATE M3U FILE
# =====================================================
m3u = f"""#EXTM3U
#EXTINF:-1 tvg-id="NTV7.my" tvg-name="NTV7" group-title="Malaysia",NTV7
{found_url}
"""

with open(
    "ntv7.m3u",
    "w",
    encoding="utf-8"
) as f:
    f.write(m3u)

# =====================================================
# OUTPUT
# =====================================================
print("\n================================")
print("M3U UPDATED SUCCESSFULLY")
print(found_url)
print("================================\n")
