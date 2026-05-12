import os
import re
from playwright.sync_api import sync_playwright

EMAIL = os.getenv("TONTON_EMAIL")
PASSWORD = os.getenv("TONTON_PASSWORD")

TARGET = "https://watch.tonton.com.my/live/ntv7"

found = None

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False,  # better for GitHub Actions anti-bot
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu"
        ]
    )

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        viewport={
            "width": 1366,
            "height": 768
        }
    )

    page = context.new_page()

    # =====================================================
    # CAPTURE ALL RESPONSES FROM ENTIRE CONTEXT
    # =====================================================
    def handle_response(response):
        global found

        try:
            url = response.url

            print(url)

            # Detect ANY m3u8
            if ".m3u8" in url:

                # Prefer authenticated URL
                if "bpkio_sessionid" in url:

                    found = url

                    print("\n================================")
                    print("FOUND STREAM URL")
                    print(url)
                    print("================================\n")

        except Exception as e:
            print(e)

    # IMPORTANT
    context.on("response", handle_response)

    # =====================================================
    # OPEN TONTON
    # =====================================================
    print("Opening homepage...")

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

    page.wait_for_selector(
        'text=Sign In',
        timeout=60000
    )

    print("Opening login popup...")

    with page.expect_popup() as popup_info:
        page.click('text=Sign In')

    popup = popup_info.value

    popup.wait_for_load_state("domcontentloaded")

    popup.wait_for_timeout(5000)

    print("Popup loaded")

    # =====================================================
    # LOGIN
    # =====================================================
    print("Entering credentials...")

    popup.wait_for_selector(
        'input[type="text"]',
        timeout=60000
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
    submit_btn = popup.locator('#submitBtn')

    box = submit_btn.bounding_box()

    if box:

        popup.mouse.move(
            box["x"] + box["width"] / 2,
            box["y"] + box["height"] / 2,
            steps=30
        )

        popup.wait_for_timeout(1000)

    print("Submitting login...")

    submit_btn.click()

    # =====================================================
    # WAIT LOGIN COMPLETE
    # =====================================================
    print("Waiting after login...")

    popup.wait_for_timeout(15000)

    try:
        popup.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass

    # =====================================================
    # CLOSE POPUP
    # =====================================================
    try:
        popup.close()
    except:
        pass

    # =====================================================
    # OPEN LIVE PAGE
    # =====================================================
    print("Opening NTV7 live page...")

    page.goto(
        TARGET,
        wait_until="domcontentloaded",
        timeout=120000
    )

    # =====================================================
    # WAIT PLAYER LOAD
    # =====================================================
    print("Waiting stream requests...")

    page.wait_for_timeout(45000)

    browser.close()

# =====================================================
# VALIDATE
# =====================================================
if not found:
    raise Exception("No stream URL found")

# =====================================================
# CLEAN URL
# =====================================================
found = found.replace("\\u0026", "&")
found = re.sub(r'\\\\u0026', '&', found)

# =====================================================
# GENERATE M3U
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
