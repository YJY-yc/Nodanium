#!/bin/bash
set -e

OWNER="YJY-yc"
REPO="Nodanium"
DEB_ASSET_NAME="nodanium_3.6.0.3_amd64.deb"

API_ENDPOINT="https://api.github.com/repos/${OWNER}/${REPO}/releases/latest"

echo "Nodanium installer starting"
echo "Fetching release metadata"

RAW_DOWNLOAD_URL=$(curl -fsSL "${API_ENDPOINT}" | grep -o "https.*${DEB_ASSET_NAME}" | head -n 1)

if [ -z "${RAW_DOWNLOAD_URL}" ]; then
    echo "error: target deb asset not found in latest release"
    exit 1
fi

# ghproxy国内加速
DOWNLOAD_URL="https://mirror.ghproxy.com/${RAW_DOWNLOAD_URL}"

TMP_DEB_FILE=$(mktemp --suffix=.deb)

echo "Downloading package"
curl -fsSL "${DOWNLOAD_URL}" -o "${TMP_DEB_FILE}"

echo "Running apt install to resolve dependencies"
sudo apt update
sudo apt install -y "${TMP_DEB_FILE}"

rm -f "${TMP_DEB_FILE}"

echo "installation finished"
echo "to remove package run: sudo apt remove nodanium"
