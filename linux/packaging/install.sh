#!/bin/sh
# Install VPN Connect from this folder into /usr/local (any distribution).
# Run: sudo ./install.sh        Author: zero.cyfa
set -eu
if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo ./install.sh" >&2
  exit 1
fi
cd "$(dirname "$0")"

missing=""
python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null \
  || missing="$missing python3-gi(GTK-3)"
command -v pkexec >/dev/null || missing="$missing pkexec(polkit)"
command -v swanctl >/dev/null || missing="$missing strongSwan(swanctl)"
if [ -n "$missing" ]; then
  echo "Missing:$missing"
  echo "Install them first:"
  echo "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-3.0 pkexec charon-systemd strongswan-swanctl libcharon-extauth-plugins"
  echo "  Fedora:        sudo dnf install python3-gobject gtk3 polkit strongswan"
  echo "  Arch:          sudo pacman -S python-gobject gtk3 polkit strongswan"
  echo "  openSUSE:      sudo zypper install python3-gobject-Gdk typelib-1_0-Gtk-3_0 polkit strongswan"
  exit 1
fi

sh packaging/install-tree.sh / /usr/local
update-mime-database /usr/local/share/mime 2>/dev/null || true
update-desktop-database -q /usr/local/share/applications 2>/dev/null || true
gtk-update-icon-cache -q -t /usr/local/share/icons/hicolor 2>/dev/null || true
echo "VPN Connect installed. Start it from the applications menu, or run: vpn-connect"
