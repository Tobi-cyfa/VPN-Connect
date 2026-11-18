# VPN Connect for Linux

**Author:** zero.cyfa

The Linux desktop version of VPN Connect. It imports any Sophos Connect `.scx` file and connects the
same IPsec tunnel as the Android app and Sophos Connect on Windows. The VPN engine is the
strongSwan package from your distribution.

## Download and install

Quickest: one terminal command, which downloads from the `linux-v0.2` release and installs.

    # Ubuntu, Debian, Mint, Pop!_OS
    wget https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect_0.2_all.deb && sudo apt install ./vpn-connect_0.2_all.deb

    # Fedora, RHEL/Alma/Rocky (with EPEL)   (openSUSE: replace "dnf" with "zypper")
    sudo dnf install https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-1.noarch.rpm

    # Arch, Manjaro
    mkdir vpn-connect && cd vpn-connect && curl -L -O https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/PKGBUILD -O https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-linux.tar.gz && makepkg -si

    # Any other distribution (into /usr/local)
    curl -L https://github.com/zero-cyfa/VPN-Connect/releases/download/linux-v0.2/vpn-connect-0.2-linux.tar.gz | tar xz && cd vpn-connect-0.2 && sudo ./install.sh

    # From the git source (latest code, into /usr/local)
    git clone https://github.com/zero-cyfa/VPN-Connect.git && sudo sh VPN-Connect/linux/packaging/install-tree.sh / /usr/local

Or download the file for your distribution from the repository's **Releases** page by hand:

| Distribution | File | Install |
|---|---|---|
| Ubuntu, Debian, Mint, Pop!_OS, elementary | `vpn-connect_0.2_all.deb` | `sudo apt install ./vpn-connect_0.2_all.deb` |
| Fedora, RHEL/Alma/Rocky (with EPEL), openSUSE | `vpn-connect-0.2-1.noarch.rpm` | `sudo dnf install ./vpn-connect-0.2-1.noarch.rpm` (openSUSE: `sudo zypper install ./…rpm`) |
| Arch, Manjaro, EndeavourOS | `PKGBUILD` + `vpn-connect-0.2-linux.tar.gz` | put both in one folder, then `makepkg -si` |
| Anything else | `vpn-connect-0.2-linux.tar.gz` | unpack, then `sudo ./install.sh` (installs into `/usr/local`) |

The packages pull in strongSwan, GTK 3, PyGObject and polkit automatically. `SHA256SUMS` lists the
checksums. The packages contain no compiled code, so they work on any CPU (x86-64, ARM).

## Using it

1. Start **VPN Connect** from the applications menu.
2. **⋮ menu > Import connection** and pick your `.scx` file. You can also drop the file on the
   window, or double-click it in the file manager. Importing a file with the same gateway or name
   updates that connection.
3. Select the connection and click **Connect**. On **Authenticate user**, type your user name and
   password and click **Sign in**.
4. Confirm the administrator prompt. Setting up an IPsec tunnel needs root, like any Linux VPN.
   The prompt is remembered for a few minutes.
5. The connection shows **Connected** with its virtual IP, DNS servers and traffic counters.
   Click **Disconnect** when done. The **Events** tab lists connects, disconnects and failures.
6. If it fails: **⋮ > Open VPN log**, then **Copy** or **Save as…**, and send the log to ICT
   support. The log shows addresses and your user name, not passwords or keys: remove your user
   name first.

Closing the window ends the VPN connection; the app asks first.

## How it works

The window runs as you. To connect, it starts a small helper as root through `pkexec`. The helper
talks to strongSwan's `charon` daemon over its control socket (VICI) and:

1. loads the IKEv1 **Main Mode** connection from the `.scx` (proposals, DPD and rekey times),
   NAT-T forced on, with a pre-shared key round and an **XAuth** round,
2. requests a virtual IP and DNS servers (**Mode Config**),
3. brings up one **Quick Mode** tunnel per network listed in the `.scx`, so only those networks
   go through the VPN,
4. when you disconnect (or the window closes), removes the tunnel, the connection, the
   pre-shared key and your password from charon again.

It starts the `strongswan` service if it is not running. Other strongSwan connections on the
computer are left alone.

## What is stored

- `~/.config/vpn-connect/connections.json` holds the imported connections, including the
  pre-shared key from the `.scx`. The file is readable only by you (mode 600). Treat the
  `.scx` file itself as confidential too.
- Your user name is remembered. **The password is never saved.** It goes to charon in memory
  only and is removed when the connection ends.
- `~/.local/state/vpn-connect/` holds the events list and the log of the last connection.

## Known limits

- IPv4 networks only, as on Android.
- DNS servers from the gateway are installed by strongSwan's `resolve` plugin, which writes
  `/etc/resolv.conf`. With systemd-resolved, internal names may not resolve while connected;
  use the IP address or add the DNS server in your network settings.
- One connection at a time.
- Tested in CI: install on Ubuntu 24.04, Debian 12, Fedora and Arch; charon accepts the
  connection the app loads; the window starts and imports a `.scx`. Connecting to a real
  Sophos Firewall from Linux still needs a first test on your network.

## Build the packages yourself

GitHub Actions: **Actions > Build Linux packages > Run workflow**. With a release tag such as
`linux-v0.2` it also publishes the release. Locally on Ubuntu or Debian:

    sudo apt install dpkg-dev rpm
    linux/packaging/build.sh          # results in linux/dist/

Run from the source folder without installing (needs `python3-gi`; connecting needs the installed
helper): `linux/bin/vpn-connect`. Unit tests: `cd linux && python3 -m unittest discover -s tests`.

## Licence

GPLv2, like strongSwan. Do not use Sophos names or logos.

VPN Connect by zero.cyfa.
