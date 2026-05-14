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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

MAX_WAIT = 90
POLL_INTERVAL = 0.5

M3U8_RE = re.compile(r'https?://[^\s\'"]*\.m3u8(?:\?[^\s\'"]*)?', re.IGNORECASE)

def extract_m3u8_from_text(text):
    if not text:
        return []
    return M3U8_RE.findall(text)
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
            # cache_valid_range reduces repeated network activity in wdm
            return ChromeDriverManager(cache_valid_range=365).install()
        except Exception:
            return None

    return None
def get_chrome_version():
    # best-effort detection of installed chrome/chromium version
    for cmd in (["google-chrome","--version"], ["chrome","--version"], ["chromium","--version"], ["google-chrome-stable","--version"]):
        exe = shutil.which(cmd[0])
        if exe:
            try:
                out = subprocess.check_output([exe, "--version"], stderr=subprocess.STDOUT)
                return out.decode(errors="ignore").strip()
            except Exception:
                continue
    return None

# =====================================================
# CREATE DRIVER
# =====================================================

def make_driver(chromedriver_path=None):
    chrome_options = Options()

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    # prefer automation flags
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
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
############################    
#  check chrome version
#########################
    chromedriver_path = find_chromedriver()
    if chromedriver_path:
        print(f"{now()} Using chromedriver: {chromedriver_path}")
    else:
        print(f"{now()} No chromedriver found in PATH or env. webdriver_manager available: {_HAS_WDM}")

    chrome_ver = get_chrome_version()
    if chrome_ver:
        print(f"{now()} Detected Chrome version: {chrome_ver}")

    driver = None
    
    
    driver = make_driver(chromedriver_path)

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
        wait = WebDriverWait(driver, 30)

        signin = wait.until(
           EC.element_to_be_clickable((
             By.XPATH,
              "//span[contains(text(),'Sign In')]/ancestor::button"
             ))
         )

        signin.click()
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

            # =========================
            # REQUEST
            # =========================
            if method == "Network.requestWillBeSent":
                url = params.get("request", {}).get("url", "") or ""

                if ".m3u8" in url.lower() and url not in found:
                    found.add(url)
                    print(f"{now()} 🟢 Found (request): {url}")

            # =========================
            # RESPONSE
            # =========================
            elif method == "Network.responseReceived":
                resp = params.get("response", {}) or {}

                url = resp.get("url", "") or ""
                mime = (resp.get("mimeType") or "").lower()

                is_m3u8 = (
                    ".m3u8" in url.lower()
                    or "mpegurl" in mime
                )

                if is_m3u8 and url not in found:
                    found.add(url)
                    print(f"{now()} 🟢 Found (response): {url}")

                # =========================
                # BODY SCAN
                # =========================
                should_fetch_body = False

                if any(url.lower().endswith(x) for x in ('.json', '.js', '.txt', '.html')):
                    should_fetch_body = True

                if any(x in mime for x in ("json", "javascript", "text", "html")):
                    should_fetch_body = True

                if resp.get("encodedDataLength", 0) > 200_000:
                    should_fetch_body = False

                if should_fetch_body:
                    request_id = params.get("requestId")

                    if request_id:
                        try:
                            body = driver.execute_cdp_cmd(
                                "Network.getResponseBody",
                                {"requestId": request_id}
                            )

                            body_text = body.get("body", "") if isinstance(body, dict) else ""

                            if body_text:
                                matches = extract_m3u8_from_text(body_text)

                                for m in matches:
                                    if m not in found:
                                        found.add(m)
                                        print(f"{now()} 🟢 Found (body): {m}")

                        except Exception:
                            pass

        if found:
            print(f"{now()} ✅ Done (found stream)")
            return list(found)

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
