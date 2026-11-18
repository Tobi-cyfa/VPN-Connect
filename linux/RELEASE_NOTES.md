## VPN Connect for Linux v0.2

The first Linux desktop version of VPN Connect, the client for Sophos Firewall IPsec VPNs.

- Import any Sophos Connect `.scx` file from the ⋮ menu, by dropping it on the window, or by
  opening it from the file manager.
- Connect with your user name and password, the same layout as the Android app: Connections and
  Events tabs, VPN log, virtual IP, DNS servers and traffic counters.
- Uses your distribution's strongSwan. One administrator prompt per connect. The password is
  never saved.
- Author: zero.cyfa

### Install from the terminal

Copy the line for your distribution into a terminal. It downloads the package from this release
and installs it together with strongSwan, GTK and polkit.

**Ubuntu, Debian, Mint, Pop!_OS, elementary**

```sh
wget https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect_0.2_all.deb && sudo apt install ./vpn-connect_0.2_all.deb
```

**Fedora, RHEL/Alma/Rocky (with EPEL)**

```sh
sudo dnf install https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-1.noarch.rpm
```

**openSUSE**

```sh
sudo zypper install https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-1.noarch.rpm
```

**Arch, Manjaro, EndeavourOS**

```sh
mkdir vpn-connect && cd vpn-connect && curl -L -O https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/PKGBUILD -O https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-linux.tar.gz && makepkg -si
```

**Any other distribution** (installs into `/usr/local`; install strongSwan, PyGObject/GTK 3 and polkit first, `install.sh` tells you if one is missing)

```sh
curl -L https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-linux.tar.gz | tar xz && cd vpn-connect-0.2 && sudo ./install.sh
```

**From the git source** (latest code, installs into `/usr/local`; same requirements as above)

```sh
git clone https://github.com/zero-cyfa/VPN-Connect.git && sudo sh VPN-Connect/linux/packaging/install-tree.sh / /usr/local
```

Then start **VPN Connect** from the applications menu, or run `vpn-connect`.

To check a download, compare it with `SHA256SUMS` from this release: `sha256sum -c SHA256SUMS --ignore-missing`.
