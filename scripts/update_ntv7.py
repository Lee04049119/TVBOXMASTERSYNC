# =====================================================
# update_ntv7.py
# =====================================================

import os
import time
import json
import re
import shutil

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# =====================================================
# ENV
# =====================================================

EMAIL = os.getenv("TONTON_EMAIL")
PASSWORD = os.getenv("TONTON_PASSWORD")

TARGET_URL = "https://watch.tonton.com.my/live/ntv7"

# =====================================================
# SETTINGS
# =====================================================

MAX_WAIT = 60
POLL_INTERVAL = 0.5

# Accept ANY authenticated Tonton playlist
M3U8_RE = re.compile(
    r'https?://[^\'"\s]+\.m3u8[^\'"\s]*',
    re.IGNORECASE
)

# =====================================================
# HELPERS
# =====================================================

def now():
    return time.strftime("%H:%M:%S")

def clean_url(url):

    # Fix escaped &
    url = url.replace("\\u0026", "&")

    # Remove duplicated backslashes
    url = url.replace("\\", "")

    return url.strip()

# =====================================================
# CHROMEDRIVER
# =====================================================

def get_chromedriver():

    env_path = os.getenv("CHROMEDRIVER_PATH")

    if env_path and os.path.exists(env_path):
        return env_path

    path = shutil.which("chromedriver")

    if path:
        return path

    return None

# =====================================================
# CREATE DRIVER
# =====================================================

def create_driver():

    options = Options()

    # GitHub Actions safer mode
    options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    options.add_argument("--window-size=1366,768")

    options.add_argument(
        "--user-agent=Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    # Chromium path for Ubuntu GitHub Actions
    chrome_bin = os.getenv("CHROME_BIN")

    if chrome_bin:
        options.binary_location = chrome_bin

    # Enable performance logs
    options.set_capability(
        "goog:loggingPrefs",
        {"performance": "ALL"}
    )

    chromedriver = get_chromedriver()

    if chromedriver:
        service = Service(chromedriver)
    else:
        service = Service()

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    driver.set_page_load_timeout(120)

    return driver

# =====================================================
# MAIN
# =====================================================

def main():

    if not EMAIL or not PASSWORD:
        raise Exception(
            "Missing TONTON_EMAIL or TONTON_PASSWORD"
        )

    print(f"{now()} Starting scraper")

    driver = create_driver()

    try:

        # =================================================
        # ENABLE NETWORK
        # =================================================

        try:
            driver.execute_cdp_cmd(
                "Network.enable",
                {}
            )
        except Exception:
            pass

        # =================================================
        # OPEN TONTON
        # =================================================

        print(f"{now()} Opening Tonton")

        driver.get("https://www.tonton.com.my")

        time.sleep(8)

        # =================================================
        # SIGN IN
        # =================================================

        print(f"{now()} Opening login")

        sign_in = driver.find_element(
            By.XPATH,
            "//*[contains(text(),'Sign In')]"
        )

        sign_in.click()

        time.sleep(8)

        # =================================================
        # SWITCH WINDOW
        # =================================================

        handles = driver.window_handles

        if len(handles) > 1:
            driver.switch_to.window(handles[-1])

        print(f"{now()} Login popup ready")

        time.sleep(5)

        # =================================================
        # LOGIN FORM
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
        # RETURN MAIN TAB
        # =================================================

        driver.switch_to.window(handles[0])

        # =================================================
        # OPEN STREAM PAGE
        # =================================================

        print(f"{now()} Opening NTV7")

        driver.get(TARGET_URL)

        time.sleep(20)

        # =================================================
        # CAPTURE STREAM
        # =================================================

        found = None
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
                # REQUEST
                # =========================================

                if method == "Network.requestWillBeSent":

                    request = params.get(
                        "request",
                        {}
                    )

                    url = request.get("url", "")

                    url_lower = url.lower()

                    # =====================================
                    # REAL TONTON STREAM DETECTION
                    # =====================================

                    if (
                        ".m3u8" in url_lower
                        and "tonton.com.my" in url_lower
                        and "bpkio_sessionid" in url
                    ):

                        found = clean_url(url)

                        print("\n================================")
                        print("FOUND STREAM URL")
                        print(found)
                        print("================================\n")

                        break

            if found:
                break

            time.sleep(POLL_INTERVAL)

        # =================================================
        # VALIDATE
        # =================================================

        if not found:
            raise Exception(
                "No authenticated stream found"
            )

        # =================================================
        # CREATE STREAMS FOLDER
        # =================================================

        os.makedirs(
            "streams",
            exist_ok=True
        )

        # =================================================
        # GENERATE M3U
        # =================================================

        m3u = f"""#EXTM3U
#EXTINF:-1 tvg-id="NTV7.my" tvg-name="NTV7" group-title="Malaysia",NTV7
#EXTVLCOPT:http-user-agent=Mozilla/5.0
#EXTVLCOPT:http-referrer=https://watch.tonton.com.my/
{found}
"""

        output = "streams/ntv7.m3u"

        with open(
            output,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(m3u)

        print("\n================================")
        print("M3U UPDATED SUCCESSFULLY")
        print(found)
        print("Saved:", output)
        print("================================\n")

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
