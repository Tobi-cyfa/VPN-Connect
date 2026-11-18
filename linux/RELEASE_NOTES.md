## VPN Connect for Linux v0.2

The first Linux desktop version of VPN Connect, the client for Sophos Firewall IPsec VPNs.

- Import any Sophos Connect `.scx` file from the ⋮ menu, by dropping it on the window, or by
  opening it from the file manager.
- Connect with your user name and password, the same layout as the Android app: Connections and
  Events tabs, VPN log, virtual IP, DNS servers and traffic counters.
- Uses your distribution's strongSwan. One administrator prompt per connect. The password is
  never saved.
- Author: zero.cyfa

### Which file do I need?

- **Ubuntu, Debian, Mint, Pop!_OS:** `vpn-connect_0.2_all.deb` → `sudo apt install ./vpn-connect_0.2_all.deb`
- **Fedora, RHEL/Alma/Rocky (EPEL), openSUSE:** `vpn-connect-0.2-1.noarch.rpm` → `sudo dnf install ./vpn-connect-0.2-1.noarch.rpm`
- **Arch, Manjaro:** `PKGBUILD` and `vpn-connect-0.2-linux.tar.gz` in one folder → `makepkg -si`
- **Other distributions:** `vpn-connect-0.2-linux.tar.gz` → unpack, `sudo ./install.sh`

Then start **VPN Connect** from the applications menu.
