#!/usr/bin/env bash
# Fetches strongSwan 6.0.7 and applies the VPN Connect changes to it.
# Author: zero.cyfa
# Usage: ./apply.sh [target-folder]      (default: ./strongswan)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HERE/strongswan}"
TAG="6.0.7"
PATCH="$HERE/patches/strongswan-android-ikev1-xauth.patch"

if [ ! -d "$TARGET/.git" ]; then
  git clone --depth 1 --branch "$TAG" https://github.com/strongswan/strongswan.git "$TARGET"
fi
TARGET="$(cd "$TARGET" && pwd)"   # make absolute: the overlay copy below runs after the cd
cd "$TARGET"

if git apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  echo "Patch already applied."
else
  git apply --check "$PATCH"
  git apply "$PATCH"
  echo "Patch applied."
fi

cp -R "$HERE/overlay/." "$TARGET/"
echo "New files copied. strongSwan tree ready in: $TARGET"
