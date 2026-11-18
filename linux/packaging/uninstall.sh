#!/bin/sh
# Remove a VPN Connect installed with install.sh. Your connections in ~/.config/vpn-connect stay.
set -eu
if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo ./uninstall.sh" >&2
  exit 1
fi
P=/usr/local
rm -rf "$P/lib/vpn-connect" "$P/share/vpn-connect" "$P/share/doc/vpn-connect"
rm -f "$P/bin/vpn-connect" "$P/share/applications/com.vpnconnect.app.desktop" \
  "$P/share/icons/hicolor/scalable/apps/vpn-connect.svg" "$P/share/mime/packages/vpn-connect.xml" \
  /usr/share/polkit-1/actions/com.vpnconnect.helper.policy
update-mime-database "$P/share/mime" 2>/dev/null || true
echo "VPN Connect removed."
