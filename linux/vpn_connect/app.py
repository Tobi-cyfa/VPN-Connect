"""VPN Connect for Linux: the window.

Same layout and wording as the Android app: Connections and Events tabs, the menu with
Import connection / Open VPN log / Help / About, and the "Authenticate user" sign-in.

Author: zero.cyfa
"""

import os
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import APP_ID, VERSION, scx  # noqa: E402
from .session import PKEXEC_DISMISSED, HelperSession  # noqa: E402
from .store import Connections, Events, VpnLog  # noqa: E402

AUTHOR = "zero.cyfa"
ICON = "vpn-connect"

ERRORS = {
    "auth": "Sign-in failed",
    "peer_auth": "The gateway did not accept the pre-shared key",
    "lookup": "Gateway address not found",
    "unreachable": "Gateway not reachable",
    "generic": "Connection error",
}

HELP = ("1. Open the ⋮ menu, choose “Import connection” and pick your .scx file "
        "(you can also drop the file on the window or open it from your file manager).\n"
        "2. Select the connection, click Connect, sign in with your user name and password, "
        "then confirm the administrator prompt.\n"
        "3. Click Disconnect when you are done.\n\n"
        "If something fails, open the VPN log from the ⋮ menu and send it to ICT support. "
        "The log shows addresses and your user name, not passwords or keys: remove your user name first.")

CSS = b"""
.vc-wordmark { font-weight: 800; letter-spacing: 2px; color: #1B87D2; }
.vc-signature { color: #8a94a3; font-size: smaller; }
.vc-title { font-size: 20px; font-weight: bold; }
.vc-sub { color: #5B6676; }
.vc-status-connected { color: #3E9A52; font-weight: bold; }
.vc-status-busy { color: #C98200; font-weight: bold; }
.vc-status-error { color: #D33A3A; font-weight: bold; }
.vc-status-idle { color: #5B6676; font-weight: bold; }
.vc-row-name { font-weight: bold; }
.vc-row-sub { color: #A0AAB6; font-size: smaller; }
.vc-row-sub-on { color: #5BAA3C; font-size: smaller; }
.vc-empty { color: #6B7480; }
"""


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" if unit == "B" else "%.1f %s") % (n, unit)
        n /= 1024.0


def human_duration(seconds):
    seconds = int(seconds)
    return "%02d:%02d:%02d" % (seconds // 3600, seconds // 60 % 60, seconds % 60)


def data_file(name):
    """Look next to the source tree first (running from a checkout), then the installed share dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.path.join(here, "..", "data"),
              os.path.join(sys.prefix, "share", "vpn-connect"),
              "/usr/share/vpn-connect", "/usr/local/share/vpn-connect"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="VPN Connect")
        self.app = app
        self.set_default_size(820, 520)
        self.set_icon_name(ICON)
        svg = data_file("vpn-connect.svg")
        if svg and not Gtk.IconTheme.get_default().has_icon(ICON):
            try:
                self.set_icon_from_file(svg)
            except GLib.Error:
                pass

        self.connections = Connections()
        self.events = Events()
        self.vpnlog = VpnLog()
        self.session = None
        self.active_id = None
        self.state = "idle"  # idle | connecting | connected | disconnecting
        self.error = {}  # connection id -> error text of the last attempt
        self.info = {}
        self.connected_since = None
        self._connected_reported = False
        self._updating = False
        self.log_window = None

        self._build_header()
        self._build_body()
        self._setup_drop()
        self.connect("delete-event", self._on_delete)
        GLib.timeout_add_seconds(1, self._tick)

        self.events.add("VPN Connect version %s" % VERSION)
        self.refresh()

    # -- layout ----------------------------------------------------------------------

    def _build_header(self):
        hb = Gtk.HeaderBar(show_close_button=True)
        self.set_titlebar(hb)
        self.header = hb

        title = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.title_label = Gtk.Label(label="VPN Connect")
        self.title_label.get_style_context().add_class("title")
        sig = Gtk.Label(label="by " + AUTHOR)
        sig.get_style_context().add_class("vc-signature")
        title.pack_start(self.title_label, False, False, 0)
        title.pack_start(sig, False, False, 0)
        hb.set_custom_title(title)

        imp = Gtk.Button.new_from_icon_name("document-open-symbolic", Gtk.IconSize.BUTTON)
        imp.set_tooltip_text("Import connection")
        imp.set_action_name("app.import")
        hb.pack_start(imp)

        menu = Gio.Menu()
        menu.append("Import connection", "app.import")
        menu.append("Open VPN log", "app.log")
        section = Gio.Menu()
        section.append("Help", "app.help")
        section.append("About", "app.about")
        section.append("Quit", "app.quit")
        menu.append_section(None, section)
        more = Gtk.MenuButton(menu_model=menu, tooltip_text="More options")
        more.add(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        hb.pack_end(more)

    def _build_body(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)

        bar = Gtk.Box(spacing=12, margin=8)
        mark = Gtk.Label(label="VPN CONNECT", xalign=0)
        mark.get_style_context().add_class("vc-wordmark")
        bar.pack_start(mark, False, False, 4)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        switcher = Gtk.StackSwitcher(stack=self.stack, halign=Gtk.Align.CENTER)
        bar.set_center_widget(switcher)
        outer.pack_start(bar, False, False, 0)
        outer.pack_start(Gtk.Separator(), False, False, 0)
        outer.pack_start(self.stack, True, True, 0)

        self.stack.add_titled(self._build_connections(), "connections", "Connections")
        self.stack.add_titled(self._build_events(), "events", "Events")

    def _build_connections(self):
        paned = Gtk.Paned(position=280)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_row_selected)
        placeholder = Gtk.Label(label="No connections", margin=20)
        placeholder.get_style_context().add_class("vc-empty")
        placeholder.show()
        self.listbox.set_placeholder(placeholder)
        sw.add(self.listbox)
        left.pack_start(sw, True, True, 0)
        paned.pack1(left, False, False)

        self.detail_stack = Gtk.Stack()
        empty = Gtk.Label(label="No connections yet.\n\nOpen the ⋮ menu, choose “Import connection” "
                                "and pick your .scx file.\nYou can also drop the file on this window.",
                          justify=Gtk.Justification.CENTER, wrap=True)
        empty.get_style_context().add_class("vc-empty")
        self.detail_stack.add_named(empty, "empty")

        d = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=24)
        top = Gtk.Box(spacing=16)
        logo = Gtk.Image.new_from_icon_name(ICON, Gtk.IconSize.DIALOG)
        svg = data_file("vpn-connect.svg")
        if svg and not Gtk.IconTheme.get_default().has_icon(ICON):
            logo = Gtk.Image.new_from_file(svg)
        logo.set_pixel_size(64)
        top.pack_start(logo, False, False, 0)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=4)
        self.d_name = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.d_name.get_style_context().add_class("vc-title")
        self.d_status = Gtk.Label(xalign=0)
        names.pack_start(self.d_name, False, False, 0)
        names.pack_start(self.d_status, False, False, 0)
        top.pack_start(names, True, True, 0)
        d.pack_start(top, False, False, 0)
        d.pack_start(Gtk.Separator(margin_top=12, margin_bottom=8), False, False, 0)

        grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        self.d_fields = {}
        for i, (key, label) in enumerate((("gateway", "Gateway"), ("networks", "Networks"),
                                          ("file", "Imported from"), ("vip", "Virtual IP"),
                                          ("dns", "DNS servers"), ("traffic", "Traffic"),
                                          ("last", "Last connected"))):
            k = Gtk.Label(label=label, xalign=0)
            k.get_style_context().add_class("vc-sub")
            v = Gtk.Label(xalign=0, selectable=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            grid.attach(k, 0, i, 1, 1)
            grid.attach(v, 1, i, 1, 1)
            self.d_fields[key] = (k, v)
        d.pack_start(grid, False, False, 0)

        buttons = Gtk.Box(spacing=8, margin_top=18)
        self.b_connect = Gtk.Button(label="Connect")
        self.b_connect.get_style_context().add_class("suggested-action")
        self.b_connect.set_size_request(140, -1)
        self.b_connect.connect("clicked", self._on_connect_clicked)
        self.b_remove = Gtk.Button(label="Remove")
        self.b_remove.connect("clicked", self._on_remove_clicked)
        buttons.pack_start(self.b_connect, False, False, 0)
        buttons.pack_end(self.b_remove, False, False, 0)
        d.pack_start(buttons, False, False, 0)

        dsw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        dsw.add(d)
        self.detail_stack.add_named(dsw, "detail")
        paned.pack2(self.detail_stack, True, False)
        return paned

    def _build_events(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.event_store = Gtk.ListStore(str, str)
        view = Gtk.TreeView(model=self.event_store)
        for i, title in enumerate(("Occurred", "Description")):
            r = Gtk.CellRendererText()
            if i == 1:
                r.set_property("ellipsize", Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(title, r, text=i)
            col.set_resizable(True)
            col.set_expand(i == 1)
            view.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.add(view)
        box.pack_start(sw, True, True, 0)
        clear = Gtk.Button(label="Clear events", halign=Gtk.Align.END, margin=8)
        clear.connect("clicked", lambda *_: (self.events.clear(), self.refresh_events()))
        box.pack_start(clear, False, False, 0)
        return box

    def _setup_drop(self):
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_add_uri_targets()
        self.connect("drag-data-received", self._on_drop)

    # -- refresh -----------------------------------------------------------------------

    def selected(self):
        return self.connections.get(self.connections.selected) if self.connections.selected else None

    def refresh(self):
        current = self.selected()
        if current is None and self.connections.items:
            self.connections.selected = self.connections.items[0]["id"]
            current = self.selected()

        self._updating = True
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        for c in self.connections.items:
            row = Gtk.ListBoxRow()
            row.cid = c["id"]
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=10, spacing=2)
            name = Gtk.Label(label=c["name"], xalign=0, ellipsize=Pango.EllipsizeMode.END)
            name.get_style_context().add_class("vc-row-name")
            on = c["id"] == self.active_id and self.state == "connected"
            sub = Gtk.Label(label=self._row_subtitle(c), xalign=0, ellipsize=Pango.EllipsizeMode.END)
            sub.get_style_context().add_class("vc-row-sub-on" if on else "vc-row-sub")
            box.pack_start(name, False, False, 0)
            box.pack_start(sub, False, False, 0)
            row.add(box)
            self.listbox.add(row)
            if current and c["id"] == current["id"]:
                self.listbox.select_row(row)
        self.listbox.show_all()
        self._updating = False

        title = (current or {}).get("file_name") or "VPN Connect"
        self.title_label.set_text(title)
        self.set_title(title if title == "VPN Connect" else "%s – VPN Connect" % title)
        self.refresh_detail()
        self.refresh_events()

    def _row_subtitle(self, c):
        if c["id"] == self.active_id:
            return {"connecting": "Connecting…", "connected": "Connected",
                    "disconnecting": "Disconnecting…"}.get(self.state, "")
        if c.get("last_connected"):
            return "Last connected " + time.strftime("%d %b %Y %H:%M", time.localtime(c["last_connected"]))
        return "Never connected"

    def refresh_detail(self):
        c = self.selected()
        if not c:
            self.detail_stack.set_visible_child_name("empty")
            return
        self.detail_stack.set_visible_child_name("detail")
        self.d_name.set_text(c["name"])
        mine = c["id"] == self.active_id
        busy = self.session is not None

        ctx = self.d_status.get_style_context()
        for cls in ("vc-status-connected", "vc-status-busy", "vc-status-error", "vc-status-idle"):
            ctx.remove_class(cls)
        if mine and self.state == "connected":
            since = time.time() - (self.connected_since or time.time())
            self.d_status.set_text("Connected  ·  " + human_duration(since))
            ctx.add_class("vc-status-connected")
        elif mine and self.state in ("connecting", "disconnecting"):
            self.d_status.set_text("Connecting…" if self.state == "connecting" else "Disconnecting…")
            ctx.add_class("vc-status-busy")
        elif self.error.get(c["id"]):
            self.d_status.set_text(self.error[c["id"]])
            ctx.add_class("vc-status-error")
        else:
            self.d_status.set_text("Disconnected")
            ctx.add_class("vc-status-idle")

        info = self.info if mine and self.state == "connected" else {}
        values = {
            "gateway": c.get("gateway", ""),
            "networks": ", ".join(c.get("networks") or []) or "None listed (all traffic)",
            "file": c.get("file_name") or "",
            "vip": ", ".join(info.get("vips") or []),
            "dns": ", ".join(info.get("dns") or []),
            "traffic": ("↓ %s   ↑ %s" % (human_bytes(info.get("bytes_in", 0)), human_bytes(info.get("bytes_out", 0)))
                        if info else ""),
            "last": (time.strftime("%d %b %Y %H:%M", time.localtime(c["last_connected"]))
                     if c.get("last_connected") else "Never connected"),
        }
        for key, (k, v) in self.d_fields.items():
            v.set_text(values[key])
            shown = bool(values[key])
            k.set_visible(shown)
            v.set_visible(shown)

        if mine and self.state in ("connected", "connecting"):
            self.b_connect.set_label("Disconnect" if self.state == "connected" else "Cancel")
            self.b_connect.set_sensitive(True)
            self.b_connect.get_style_context().remove_class("suggested-action")
            self.b_connect.get_style_context().add_class("destructive-action")
        else:
            self.b_connect.set_label("Connect")
            self.b_connect.set_sensitive(not busy)
            self.b_connect.get_style_context().remove_class("destructive-action")
            self.b_connect.get_style_context().add_class("suggested-action")
        self.b_remove.set_sensitive(not mine or not busy)

    def refresh_events(self):
        self.event_store.clear()
        for e in self.events.items:
            self.event_store.append([time.strftime("%d %b %Y %H:%M:%S", time.localtime(e["time"])), e["text"]])

    def _tick(self):
        if self.state == "connected":
            self.refresh_detail()
        return True

    # -- import ------------------------------------------------------------------------

    def import_dialog(self):
        dlg = Gtk.FileChooserNative(title="Import connection", transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN, select_multiple=True)
        f = Gtk.FileFilter()
        f.set_name("Sophos Connect files (.scx)")
        f.add_pattern("*.scx")
        f.add_pattern("*.SCX")
        dlg.add_filter(f)
        every = Gtk.FileFilter()
        every.set_name("All files")
        every.add_pattern("*")
        dlg.add_filter(every)
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.import_files([g.get_path() for g in dlg.get_files() if g.get_path()])
        dlg.destroy()

    def import_files(self, paths):
        messages, ok = [], True
        for path in paths:
            try:
                profile = scx.read_file(path)
            except OSError:
                messages.append("Could not read %s." % os.path.basename(path))
                ok = False
                continue
            except scx.ScxError:
                messages.append("%s is not a usable Sophos Connect (.scx) file." % os.path.basename(path))
                ok = False
                continue
            entry, created = self.connections.add_or_update(profile, os.path.basename(path))
            messages.append(("Imported “%s”. Select it, then Connect." if created else "Updated “%s”.")
                            % entry["name"])
        if messages:
            self.refresh()
            self.message("Import connection", "\n\n".join(messages),
                         Gtk.MessageType.INFO if ok else Gtk.MessageType.WARNING)

    def _on_drop(self, widget, context, x, y, data, info, time_):
        paths = []
        for uri in data.get_uris() or []:
            path, _ = GLib.filename_from_uri(uri)
            if path:
                paths.append(path)
        self.import_files(paths)

    # -- connect / disconnect ----------------------------------------------------------

    def _on_row_selected(self, listbox, row):
        if getattr(self, "_updating", False) or row is None:
            return
        self.connections.selected = row.cid
        self.connections.save()
        c = self.selected()
        title = (c or {}).get("file_name") or "VPN Connect"
        self.title_label.set_text(title)
        self.refresh_detail()

    def _on_connect_clicked(self, *_):
        c = self.selected()
        if not c:
            return
        if self.session and c["id"] == self.active_id:
            self.state = "disconnecting"
            self.session.disconnect()
            self.refresh()
            return
        problem = HelperSession.available()
        if problem:
            self.message("VPN Connect", problem, Gtk.MessageType.ERROR)
            return
        creds = self.ask_credentials(c)
        if not creds:
            return
        username, password = creds
        if username != c.get("username"):
            c["username"] = username
            self.connections.save()

        self.error.pop(c["id"], None)
        self.info = {}
        self.active_id = c["id"]
        self.state = "connecting"
        self._connected_reported = False
        self.vpnlog.start()
        self.session = HelperSession(
            lambda msg: GLib.idle_add(self._on_helper_message, msg),
            lambda code: GLib.idle_add(self._on_helper_exit, code))
        try:
            self.session.start(c, username, password)
        except OSError as e:
            self.session = None
            self.state = "idle"
            self._fail(c, "Could not start the VPN helper: %s" % e)
        password = None
        self.refresh()

    def ask_credentials(self, c):
        dlg = Gtk.Dialog(title="Authenticate user", transient_for=self, modal=True)
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        sign_in = dlg.add_button("Sign in", Gtk.ResponseType.OK)
        sign_in.get_style_context().add_class("suggested-action")
        dlg.set_default_response(Gtk.ResponseType.OK)

        box = dlg.get_content_area()
        box.set_spacing(8)
        box.set_border_width(18)
        head = Gtk.Label(xalign=0)
        head.set_markup("<b>Please enter user credentials</b>")
        box.add(head)
        box.add(Gtk.Label(label="To connect to “%s”, enter your user name and password and click Sign in."
                          % c["name"], xalign=0, wrap=True, max_width_chars=48))
        user = Gtk.Entry(placeholder_text="User name", text=c.get("username") or "", activates_default=True)
        pw = Gtk.Entry(placeholder_text="Password", visibility=False, activates_default=True,
                       input_purpose=Gtk.InputPurpose.PASSWORD)
        box.add(user)
        box.add(pw)

        def update(*_):
            sign_in.set_sensitive(bool(user.get_text().strip()) and bool(pw.get_text()))
        user.connect("changed", update)
        pw.connect("changed", update)
        update()
        dlg.show_all()
        (pw if user.get_text() else user).grab_focus()

        result = None
        if dlg.run() == Gtk.ResponseType.OK and user.get_text().strip() and pw.get_text():
            result = (user.get_text().strip(), pw.get_text())
        pw.set_text("")
        dlg.destroy()
        return result

    def _on_helper_message(self, msg):
        kind = msg.get("type")
        c = self.connections.get(self.active_id) if self.active_id else None
        if kind == "log":
            self.vpnlog.append(str(msg.get("line", "")))
            if self.log_window:
                self.log_window.reload()
        elif kind == "state":
            state = msg.get("state")
            if state == "connected":
                self.state = "connected"
                self.connected_since = time.time()
                self.info = {"vips": msg.get("vips") or [], "dns": msg.get("dns") or []}
                self._connected_reported = True
                if c:
                    c["last_connected"] = time.time()
                    self.connections.save()
                    self.events.add("Connected to “%s”" % c["name"])
                    tunnels, networks = msg.get("tunnels", 0), msg.get("networks", 0)
                    if networks and tunnels < networks:
                        self.events.add("“%s”: %d of %d networks were refused by the gateway"
                                        % (c["name"], networks - tunnels, networks))
            elif state == "disconnecting":
                self.state = "disconnecting"
            elif state == "disconnected":
                self._finish(c, msg)
            self.refresh()
        elif kind == "stats":
            self.info.update({k: msg.get(k) for k in ("bytes_in", "bytes_out", "vips", "tunnels")})
            self.refresh_detail()
        return False

    def _finish(self, c, msg):
        error = msg.get("error")
        if c:
            if self._connected_reported:
                self.events.add("Disconnected from “%s”" % c["name"])
            if error:
                text = msg.get("message") if error == "generic" and msg.get("message") else ERRORS.get(error)
                if msg.get("lost"):
                    text = "The VPN connection was lost"
                self._fail(c, text or ERRORS["generic"])
        self._connected_reported = False
        self.state = "idle"

    def _fail(self, c, text):
        self.error[c["id"]] = text
        self.events.add("“%s”: %s" % (c["name"], text))

    def _on_helper_exit(self, code):
        c = self.connections.get(self.active_id) if self.active_id else None
        if self.state != "idle" and c:
            # the helper ended without reporting the end of the session
            if code in PKEXEC_DISMISSED and not self._connected_reported:
                self.error[c["id"]] = "Administrator authorisation was cancelled"
                self.events.add("“%s”: administrator authorisation was cancelled" % c["name"])
            else:
                self._finish(c, {"error": "generic", "message": "The VPN helper stopped (exit code %s)" % code})
        self.state = "idle"
        self.session = None
        self.active_id = None
        self.info = {}
        self.refresh()
        return False

    def _on_remove_clicked(self, *_):
        c = self.selected()
        if not c:
            return
        dlg = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE, text="Remove connection?")
        dlg.format_secondary_text("“%s” and its saved settings will be deleted from this computer." % c["name"])
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Remove", Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        if dlg.run() == Gtk.ResponseType.OK:
            self.connections.remove(c["id"])
            self.error.pop(c["id"], None)
            self.refresh()
        dlg.destroy()

    # -- other windows -------------------------------------------------------------------

    def message(self, title, text, kind=Gtk.MessageType.INFO):
        dlg = Gtk.MessageDialog(transient_for=self, modal=True, message_type=kind,
                                buttons=Gtk.ButtonsType.CLOSE, text=title)
        dlg.format_secondary_text(text)
        dlg.run()
        dlg.destroy()

    def show_log(self):
        if not self.log_window:
            self.log_window = LogWindow(self)
            self.log_window.connect("destroy", lambda *_: setattr(self, "log_window", None))
        self.log_window.present()

    def show_about(self):
        about = Gtk.AboutDialog(transient_for=self, modal=True, program_name="VPN Connect", version=VERSION,
                                logo_icon_name=ICON, authors=[AUTHOR],
                                comments="Connects to IPsec VPNs on Sophos Firewall, using the Sophos "
                                         "Connect (.scx) file you import.\n\nVPN engine: strongSwan, "
                                         "licensed under GPLv2. This app is distributed under the same licence.",
                                license_type=Gtk.License.GPL_2_0)
        about.run()
        about.destroy()

    def _on_delete(self, *_):
        if not self.session:
            return False
        dlg = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                buttons=Gtk.ButtonsType.NONE, text="Disconnect and quit?")
        dlg.format_secondary_text("Closing VPN Connect ends the VPN connection.")
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Disconnect and quit", Gtk.ResponseType.OK)
        answer = dlg.run()
        dlg.destroy()
        if answer != Gtk.ResponseType.OK:
            return True
        self.shutdown_session()
        return False

    def shutdown_session(self):
        if self.session:
            self.session.close()
            self.session.wait(8)
            if self._connected_reported and self.active_id:
                c = self.connections.get(self.active_id)
                if c:
                    self.events.add("Disconnected from “%s”" % c["name"])
            self.session = None


class LogWindow(Gtk.Window):
    def __init__(self, parent):
        super().__init__(title="VPN log", transient_for=parent)
        self.parent_window = parent
        self.set_default_size(760, 460)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(box)
        self.view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                 left_margin=8, right_margin=8, top_margin=8)
        sw = Gtk.ScrolledWindow()
        sw.add(self.view)
        box.pack_start(sw, True, True, 0)
        buttons = Gtk.Box(spacing=8, margin=8)
        for label, handler in (("Copy", self.copy), ("Save as…", self.save), ("Close", lambda *_: self.destroy())):
            b = Gtk.Button(label=label)
            b.connect("clicked", handler)
            buttons.pack_end(b, False, False, 0) if label == "Close" else buttons.pack_start(b, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        self.reload()
        self.show_all()

    def reload(self):
        text = self.parent_window.vpnlog.read() or "The log is empty."
        buf = self.view.get_buffer()
        buf.set_text(text)
        self.view.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 1)

    def copy(self, *_):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.parent_window.vpnlog.read(), -1)

    def save(self, *_):
        dlg = Gtk.FileChooserNative(title="Save VPN log", transient_for=self, action=Gtk.FileChooserAction.SAVE,
                                    do_overwrite_confirmation=True)
        dlg.set_current_name("vpn-connect-log.txt")
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            with open(dlg.get_filename(), "w", encoding="utf-8") as f:
                f.write(self.parent_window.vpnlog.read())
        dlg.destroy()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        GLib.set_application_name("VPN Connect")
        GLib.set_prgname("vpn-connect")
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for name, handler in (("import", lambda *_: self.window.import_dialog()),
                              ("log", lambda *_: self.window.show_log()),
                              ("help", lambda *_: self.window.message("Help", HELP)),
                              ("about", lambda *_: self.window.show_about()),
                              ("quit", self._quit)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
        self.set_accels_for_action("app.import", ["<Control>o"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def do_activate(self):
        if not self.window:
            self.window = Window(self)
            self.window.show_all()
            self.window.refresh_detail()
        self.window.present()

    def do_open(self, files, n_files, hint):
        self.do_activate()
        self.window.import_files([f.get_path() for f in files if f.get_path()])

    def _quit(self, *_):
        if self.window and self.window._on_delete():
            return
        if self.window:
            self.window.destroy()
        self.quit()

    def do_shutdown(self):
        if self.window:
            self.window.shutdown_session()
        Gtk.Application.do_shutdown(self)


def main(argv=None):
    return App().run(argv if argv is not None else sys.argv)
