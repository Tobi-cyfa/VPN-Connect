#!/bin/sh
# Install VPN Connect into DESTDIR with PREFIX (default /usr). Used by all packages.
# Usage: install-tree.sh DESTDIR [PREFIX]          Author: zero.cyfa
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:?usage: install-tree.sh DESTDIR [PREFIX]}
DEST=${DEST%/}
PREFIX=${2:-/usr}
LIB="$PREFIX/lib/vpn-connect"
HELPER="$LIB/vpn-connect-helper"

install -d "$DEST$LIB/vpn_connect" "$DEST$PREFIX/bin" \
  "$DEST$PREFIX/share/applications" "$DEST$PREFIX/share/icons/hicolor/scalable/apps" \
  "$DEST$PREFIX/share/mime/packages" "$DEST$PREFIX/share/vpn-connect" \
  "$DEST$PREFIX/share/doc/vpn-connect" "$DEST/usr/share/polkit-1/actions"

install -m 0644 "$SRC"/vpn_connect/*.py "$DEST$LIB/vpn_connect/"
install -m 0755 "$SRC/bin/vpn-connect-helper" "$DEST$HELPER"
install -m 0755 "$SRC/bin/vpn-connect" "$DEST$PREFIX/bin/vpn-connect"
install -m 0644 "$SRC/data/com.vpnconnect.app.desktop" "$DEST$PREFIX/share/applications/"
install -m 0644 "$SRC/data/vpn-connect.svg" "$DEST$PREFIX/share/icons/hicolor/scalable/apps/vpn-connect.svg"
install -m 0644 "$SRC/data/vpn-connect.svg" "$DEST$PREFIX/share/vpn-connect/vpn-connect.svg"
install -m 0644 "$SRC/data/vpn-connect-mime.xml" "$DEST$PREFIX/share/mime/packages/vpn-connect.xml"
install -m 0644 "$SRC/README.md" "$DEST$PREFIX/share/doc/vpn-connect/README.md"

# polkit only reads actions from /usr/share; the policy names the exact helper path pkexec may run
sed "s|@HELPER@|$HELPER|" "$SRC/data/com.vpnconnect.helper.policy" \
  > "$DEST/usr/share/polkit-1/actions/com.vpnconnect.helper.policy"
chmod 0644 "$DEST/usr/share/polkit-1/actions/com.vpnconnect.helper.policy"
