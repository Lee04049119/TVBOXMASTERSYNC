import os
import sys
import time
import json
import re
import shutil

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _HAS_WDM = True
except Exception:
    _HAS_WDM = False


# =====================================================
# CONFIG
# =====================================================

EMAIL = os.getenv("TONTON_EMAIL")
PASSWORD = os.getenv("TONTON_PASSWORD")


MAX_WAIT = 90
POLL_INTERVAL = 0.5
TARGET_URL = "https://watch.tonton.com.my/live/ntv7"
M3U8_RE = re.compile(r'https?://[^\s\'"]+\.m3u8[^\s\'"]*', re.IGNORECASE)


# =====================================================
# HELPERS
# =====================================================

def now():
    return time.strftime("%H:%M:%S")


def find_chromedriver():
    env_path = os.getenv("CHROMEDRIVER_PATH")

    if env_path and os.path.exists(env_path):
        return env_path

    path = shutil.which("chromedriver")
    if path:
        return path

    if _HAS_WDM:
        try:
            return ChromeDriverManager().install()
        except Exception:
            pass

    return None


# =====================================================
# CREATE DRIVER
# =====================================================

def make_driver():
    chrome_options = Options()

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    chrome_options.set_capability(
        "goog:loggingPrefs",
        {"performance": "ALL"}
    )

    driver_path = find_chromedriver()
    service = Service(driver_path) if driver_path else Service()

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(120)

    return driver


# =====================================================
# MAIN
# =====================================================

def main():
    if not EMAIL or not PASSWORD:
        raise Exception("Missing TONTON_EMAIL or TONTON_PASSWORD")

    print(f"{now()} Starting capture")

    driver = make_driver()

    try:
        # Enable network logs
        try:
            driver.execute_cdp_cmd("Network.enable", {})
        except Exception:
            pass

        # Open homepage
        print(f"{now()} Opening homepage")
        driver.get("https://www.tonton.com.my")
        time.sleep(8)

        # Click Sign In
        print(f"{now()} Opening login")
        driver.find_element(By.XPATH, "//*[contains(text(),'Sign In')]").click()
        time.sleep(8)

        # Switch popup
        handles = driver.window_handles
        if len(handles) > 1:
            driver.switch_to.window(handles[-1])

        time.sleep(5)

        # Login
        driver.find_element(By.CSS_SELECTOR, 'input[type="text"]').send_keys(EMAIL)
        driver.find_element(By.CSS_SELECTOR, 'input[type="password"]').send_keys(PASSWORD)
        time.sleep(1)
        driver.find_element(By.ID, "submitBtn").click()

        print(f"{now()} Logged in")
        time.sleep(10)

        # Back to main window
        driver.switch_to.window(handles[0])

        # Open live page
        print(f"{now()} Opening stream")
        driver.get(TARGET_URL)
        time.sleep(10)

        # Try force play
        try:
            driver.execute_script("""
                let v = document.querySelector('video');
                if (v) { v.muted = true; v.play(); }
            """)
            print(f"{now()} Triggered video play")
        except Exception:
            pass

        time.sleep(5)

        # Capture m3u8
        found = set()
        processed = set()

        start = time.time()

        print(f"{now()} Capturing streams...")

        while time.time() - start < MAX_WAIT:
            try:
                logs = driver.get_log("performance")
            except Exception:
                logs = []

            for entry in logs:
                raw = entry.get("message")
                if not raw or raw in processed:
                    continue

                processed.add(raw)

                try:
                    msg = json.loads(raw)["message"]
                except Exception:
                    continue

                method = msg.get("method", "")
                params = msg.get("params", {})

                if method in ["Network.requestWillBeSent", "Network.responseReceived"]:
                    url = ""

                    if method == "Network.requestWillBeSent":
                        url = params.get("request", {}).get("url", "")
                    else:
                        url = params.get("response", {}).get("url", "")

                    if ".m3u8" in url.lower():
                        clean_url = re.sub(r'\\u0026', '&', url)

                        if clean_url not in found:
                            found.add(clean_url)
                            print(f"\n{now()} FOUND:\n{clean_url}\n")

            time.sleep(POLL_INTERVAL)

        if not found:
            print("❌ No stream found")
            sys.exit(1)

        # Prefer highest quality playlist
        stream_url = sorted(found, key=len, reverse=True)[0]

        print("\n================================")
        print("FINAL STREAM URL")
        print(stream_url)
        print("================================\n")

        # Save M3U
        m3u = f"""#EXTM3U
#EXTINF:-1 tvg-id="NTV7.my" tvg-name="NTV7" group-title="Malaysia",NTV7
#EXTVLCOPT:http-user-agent=Mozilla/5.0
#EXTVLCOPT:http-referrer=https://watch.tonton.com.my/
{stream_url}
"""

        with open("streams/ntv7.m3u", "w", encoding="utf-8") as f:
            f.write(m3u)

        print("✅ Saved ntv7.m3u")

    finally:
        try:
            driver.quit()
        except Exception:
            pass


# =====================================================
# START
# =====================================================

if __name__ == "__main__":
    main()
