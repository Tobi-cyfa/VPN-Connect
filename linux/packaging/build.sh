#!/bin/bash
# Build the Linux release: .deb, .rpm, .tar.gz and an Arch PKGBUILD in linux/dist/.
# Needs dpkg-deb and rpmbuild (Ubuntu: sudo apt install dpkg-dev rpm).   Author: zero.cyfa
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c 'import vpn_connect; print(vpn_connect.VERSION)')
DIST=$PWD/dist
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
rm -rf "$DIST"
mkdir -p "$DIST"
find . -name __pycache__ -prune -exec rm -rf {} +
chmod 0755 bin/* packaging/*.sh

# --- .deb (Debian, Ubuntu, Mint, Pop!_OS, elementary ...) ---
ROOT=$WORK/deb
packaging/install-tree.sh "$ROOT" /usr
mkdir -p "$ROOT/DEBIAN"
SIZE=$(du -sk "$ROOT" | cut -f1)
sed -e "s/@VERSION@/$VERSION/" -e "s/@SIZE@/$SIZE/" packaging/debian/control > "$ROOT/DEBIAN/control"
install -m 0755 packaging/debian/postinst "$ROOT/DEBIAN/postinst"
install -m 0755 packaging/debian/postinst "$ROOT/DEBIAN/postrm"
dpkg-deb --root-owner-group --build "$ROOT" "$DIST/vpn-connect_${VERSION}_all.deb"

# --- .rpm (Fedora, RHEL/Alma/Rocky with EPEL, openSUSE) ---
mkdir -p "$WORK/rpm/BUILD" "$WORK/rpm/RPMS" "$WORK/rpm/SOURCES" "$WORK/rpm/SPECS" "$WORK/rpm/SRPMS"
SRCDIR=$WORK/src/vpn-connect-$VERSION
mkdir -p "$SRCDIR"
cp -r bin data vpn_connect packaging README.md "$SRCDIR/"
tar -C "$WORK/src" -czf "$WORK/rpm/SOURCES/vpn-connect-$VERSION.tar.gz" "vpn-connect-$VERSION"
sed "s/@VERSION@/$VERSION/" packaging/rpm/vpn-connect.spec > "$WORK/rpm/SPECS/vpn-connect.spec"
rpmbuild --define "_topdir $WORK/rpm" -bb "$WORK/rpm/SPECS/vpn-connect.spec"
cp "$WORK"/rpm/RPMS/noarch/*.rpm "$DIST/"

# --- .tar.gz (any distribution: sudo ./install.sh) ---
install -m 0755 packaging/install.sh "$SRCDIR/install.sh"
install -m 0755 packaging/uninstall.sh "$SRCDIR/uninstall.sh"
tar -C "$WORK/src" -czf "$DIST/vpn-connect-$VERSION-linux.tar.gz" "vpn-connect-$VERSION"

# --- Arch Linux: PKGBUILD for the tarball ---
SUM=$(sha256sum "$DIST/vpn-connect-$VERSION-linux.tar.gz" | cut -d' ' -f1)
sed -e "s/@VERSION@/$VERSION/" -e "s/@SHA256@/$SUM/" packaging/arch/PKGBUILD > "$DIST/PKGBUILD"

(cd "$DIST" && sha256sum -- * > SHA256SUMS)
ls -l "$DIST"
