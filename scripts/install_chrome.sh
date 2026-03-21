#!/bin/bash
# Init script: installs Google Chrome and ChromeDriver for Selenium.
# Upload to Databricks workspace at: /Shared/property-data-platform/install_chrome.sh
set -euo pipefail

apt-get update -qq
apt-get install -y wget xvfb

wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb
