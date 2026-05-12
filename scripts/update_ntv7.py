import os
import sys
import time
import json
import re
import shutil
import subprocess

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

TARGET_URL = "https://watch.tonton.com.my/live/ntv7"

MAX_WAIT = 40
POLL_INTERVAL = 0.5

M3U8_RE = re.compile(
    r'https?://[^\'"\s>]+\.m3u8[^\'"\s>]*',
    flags=re.IGNORECASE
)

# =====================================================
# HELPERS
# =====================================================

def now():
    return time.strftime("%H:%M:%S")

def extract_m3u8(text):
    if not text:
        return []
    return M3U8_RE.findall(text)

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

    if driver_path:
        service = Service(driver_path)
    else:
        service = Service()

    driver = webdriver.Chrome(
        service=service,
        options=chrome_options
    )

    driver.set_page_load_timeout(120)

    return driver

# =====================================================
# MAIN
# =====================================================

def main():

    if not EMAIL or not PASSWORD:
        raise Exception("Missing TONTON_EMAIL or TONTON_PASSWORD")

    print(f"{now()} Starting Tonton capture")

    driver = make_driver()

    try:

        # =================================================
        # ENABLE NETWORK LOGGING
        # =================================================

        try:
            driver.execute_cdp_cmd("Network.enable", {})
        except Exception:
            pass

        # =================================================
        # OPEN HOMEPAGE
        # =================================================

        print(f"{now()} Opening homepage")

        driver.get("https://www.tonton.com.my")

        time.sleep(8)

        # =================================================
        # CLICK SIGN IN
        # =================================================

        print(f"{now()} Opening login popup")

        sign_in = driver.find_element(
            By.XPATH,
            "//*[contains(text(),'Sign In')]"
        )

        sign_in.click()

        time.sleep(8)

        # =================================================
        # SWITCH POPUP
        # =================================================

        handles = driver.window_handles

        if len(handles) > 1:
            driver.switch_to.window(handles[-1])

        print(f"{now()} Login popup ready")

        time.sleep(5)

        # =================================================
        # LOGIN
        # =================================================

        email_input = driver.find_element(
            By.CSS_SELECTOR,
            'input[type="text"]'
        )

        password_input = driver.find_element(
            By.CSS_SELECTOR,
            'input[type="password"]'
        )

        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)

        time.sleep(1)

        submit_btn = driver.find_element(
            By.ID,
            "submitBtn"
        )

        submit_btn.click()

        print(f"{now()} Login submitted")

        time.sleep(10)

        # =================================================
        # RETURN MAIN WINDOW
        # =================================================

        driver.switch_to.window(handles[0])

        # =================================================
        # OPEN LIVE PAGE
        # =================================================

        print(f"{now()} Opening live stream")

        driver.get(TARGET_URL)

        time.sleep(15)

        # =================================================
        # CAPTURE M3U8
        # =================================================

        found = set()
        processed = set()

        start = time.time()

        while time.time() - start < MAX_WAIT:

            try:
                logs = driver.get_log("performance")
            except Exception:
                logs = []

            for entry in logs:

                raw = entry.get("message")

                if not raw:
                    continue

                if raw in processed:
                    continue

                processed.add(raw)

                try:
                    msg = json.loads(raw)["message"]
                except Exception:
                    continue

                method = msg.get("method", "")
                params = msg.get("params", {})

                # =========================================
                # REQUEST URL
                # =========================================

                if method == "Network.requestWillBeSent":

                    url = (
                        params.get("request", {})
                        .get("url", "")
                    )

                    if (
                        ".m3u8" in url.lower()
                        and "bpkio_sessionid" in url
                    ):

                        if url not in found:

                            found.add(url)

                            print(
                                f"\n{now()} FOUND STREAM:\n{url}\n"
                            )

                # =========================================
                # RESPONSE URL
                # =========================================

                elif method == "Network.responseReceived":

                    resp = params.get("response", {})

                    url = resp.get("url", "")

                    if (
                        ".m3u8" in url.lower()
                        and "bpkio_sessionid" in url
                    ):

                        if url not in found:

                            found.add(url)

                            print(
                                f"\n{now()} FOUND RESPONSE:\n{url}\n"
                            )

            if found:
                break

            time.sleep(POLL_INTERVAL)

        # =================================================
        # OUTPUT M3U
        # =================================================

        if not found:

            print("No stream found")
            sys.exit(1)

        stream_url = sorted(found)[0]

        stream_url = re.sub(
            r'\\u0026',
            '&',
            stream_url
        )

        print("\n================================")
        print("FINAL STREAM URL")
        print(stream_url)
        print("================================\n")

        m3u = f"""#EXTM3U
#EXTINF:-1 tvg-id="NTV7.my" tvg-name="NTV7" group-title="Malaysia",NTV7
#EXTVLCOPT:http-user-agent=Mozilla/5.0
#EXTVLCOPT:http-referrer=https://watch.tonton.com.my/
{stream_url}
"""

        with open(
            "ntv7.m3u",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(m3u)

        print("M3U file saved: ntv7.m3u")

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
