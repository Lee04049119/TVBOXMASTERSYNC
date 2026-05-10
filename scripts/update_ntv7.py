import os
from playwright.sync_api import sync_playwright

EMAIL = os.getenv("TONTON_EMAIL")
PASSWORD = os.getenv("TONTON_PASSWORD")

TARGET = "https://watch.tonton.com.my/live/ntv7"

found = None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Open login page
    page.goto("https://www.tonton.com.my")

    # Click login
    page.click('text=Log In')

    # Fill login form
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASSWORD)

    # Submit
    page.click('button[type="submit"]')

    page.wait_for_load_state("networkidle")

    def handle_response(response):
        global found
        url = response.url

        if ".m3u8" in url and "ntv7" in url:
            found = url

    page.on("response", handle_response)

    # Open live page
    page.goto(TARGET, wait_until="networkidle")

    browser.close()

if not found:
    raise Exception("No stream URL found")

m3u = f"""#EXTM3U
#EXTINF:-1 tvg-id="NTV7.my",NTV7
{found}
"""

with open("ntv7.m3u", "w", encoding="utf-8") as f:
    f.write(m3u)

print(found)
