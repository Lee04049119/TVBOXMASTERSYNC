name: Fetch Tonton Stream URL

on:
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest

    steps:

      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      # ==================================================
      # INSTALL CHROMIUM
      # ==================================================

      - name: Install Chromium + Chromedriver
        run: |
          sudo apt-get update

          sudo apt-get install -y \
            chromium-browser \
            chromium-chromedriver \
            unzip \
            wget \
            curl

          echo "CHROME_BIN=$(which chromium-browser)" >> $GITHUB_ENV
          echo "CHROMEDRIVER_PATH=$(which chromedriver)" >> $GITHUB_ENV

          echo "========== VERSION =========="
          chromium-browser --version || true
          chromedriver --version || true
          echo "============================="

      # ==================================================
      # INSTALL PYTHON DEPENDENCIES
      # ==================================================

      - name: Install Python packages
        run: |
          python -m pip install --upgrade pip
          pip install selenium webdriver-manager

      # ==================================================
      # RUN SCRIPT
      # ==================================================

      - name: Run Tonton scraper
        env:
          TONTON_EMAIL: ${{ secrets.TONTON_EMAIL }}
          TONTON_PASSWORD: ${{ secrets.TONTON_PASSWORD }}

          CHROMEDRIVER_PATH: ${{ env.CHROMEDRIVER_PATH }}

        run: |
          echo "Starting scraper..."

          python fetch_stream.py 2>&1 | tee output.txt

      # ==================================================
      # UPLOAD LOG
      # ==================================================

      - name: Upload output log
        uses: actions/upload-artifact@v4
        with:
          name: tonton-log
          path: output.txt

      # ==================================================
      # UPLOAD M3U
      # ==================================================

      - name: Upload M3U file
        uses: actions/upload-artifact@v4
        with:
          name: ntv7-m3u
          path: ntv7.m3u
