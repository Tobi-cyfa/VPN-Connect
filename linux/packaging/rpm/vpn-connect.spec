Name:           vpn-connect
Version:        @VERSION@
Release:        1
Summary:        IPsec VPN client for Sophos Firewall (.scx profiles)
License:        GPL-2.0-or-later
URL:            https://github.com/Tobi-cyfa/VPN-Connect
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3 >= 3.8
Requires:       (python3-gobject or python3-gobject-base or python3-gobject-Gdk)
Requires:       (gtk3 or libgtk-3-0)
Requires:       (polkit or polkit-pkexec)
Requires:       strongswan
%global debug_package %{nil}
%global __brp_mangle_shebangs %{nil}

%description
VPN Connect imports a Sophos Connect .scx file and connects the same IPsec
tunnel Sophos Connect makes on Windows: IKEv1 Main Mode with a pre-shared key,
XAuth user name and password, Mode Config and one tunnel per listed network.
The VPN engine is strongSwan. Author: zero.cyfa

%prep
%setup -q

%build

%install
sh packaging/install-tree.sh %{buildroot} /usr

%files
/usr/bin/vpn-connect
/usr/lib/vpn-connect
/usr/share/applications/com.vpnconnect.app.desktop
/usr/share/icons/hicolor/scalable/apps/vpn-connect.svg
/usr/share/mime/packages/vpn-connect.xml
/usr/share/vpn-connect
/usr/share/polkit-1/actions/com.vpnconnect.helper.policy
%doc /usr/share/doc/vpn-connect/README.md

%post
update-mime-database /usr/share/mime >/dev/null 2>&1 || :
update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || :

%postun
update-mime-database /usr/share/mime >/dev/null 2>&1 || :
