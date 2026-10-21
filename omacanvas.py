#!/usr/bin/env python3
"""OmaCanvas: a locked-down Canvas window for Omarchy.

Opens only the school's Canvas and the hosts listed in the config. There is no
address bar, and every other site is blocked, so this app can't be used as a
general web browser.
"""

import json
import os
import sys
from urllib.parse import urlparse

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

import turnin  # noqa: E402

APP_ID = "org.pacificachristian.OmaCanvas"
SYSTEM_CONFIG = "/etc/omacanvas/config.json"
BUNDLED_CONFIG = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "omacanvas")
CACHE_DIR = os.path.join(GLib.get_user_cache_dir(), "omacanvas")


def load_config():
    # The admin-owned system config always wins. Students can't edit it, and
    # there is no env var or flag override that could point the app elsewhere.
    path = SYSTEM_CONFIG if os.path.exists(SYSTEM_CONFIG) else BUNDLED_CONFIG
    with open(path) as f:
        cfg = json.load(f)
    canvas_host = urlparse(cfg["canvas_url"]).hostname
    cfg["allowed_hosts"] = [canvas_host] + cfg.get("allowed_hosts", [])
    cfg["embed_hosts"] = cfg.get("embed_hosts", [])
    return cfg


def host_matches(uri, hosts):
    host = urlparse(uri).hostname or ""
    return any(host == h or host.endswith("." + h) for h in hosts)


def is_web(uri):
    return urlparse(uri).scheme in ("http", "https")


def content_filter_rules(hosts):
    # WebKit content-blocker rules: block every http(s) page or frame document,
    # then let the listed hosts through. Scripts, images and styles from other
    # hosts (CDNs) still load. Pages only open where we allow.
    rules = [{"trigger": {"url-filter": "^https?://", "resource-type": ["document"]},
              "action": {"type": "block"}},
             {"trigger": {"url-filter": "^file:"}, "action": {"type": "block"}}]
    for h in hosts:
        pattern = "^https?://([^/]*\\.)?" + h.replace(".", "\\.") + "[:/]"
        rules.append({"trigger": {"url-filter": pattern}, "action": {"type": "ignore-previous-rules"}})
    return json.dumps(rules)


class CanvasWindow(Gtk.ApplicationWindow):
    def __init__(self, app, related=None):
        super().__init__(application=app, title="Canvas")
        self.app = app
        self.set_default_size(1280, 860)
        self.set_icon_name("omacanvas")

        if related:
            self.view = WebKit2.WebView.new_with_related_view(related)
        else:
            self.view = WebKit2.WebView(web_context=app.context, user_content_manager=app.content)
            settings = self.view.get_settings()
            settings.set_enable_developer_extras(False)
            settings.set_enable_back_forward_navigation_gestures(True)
            settings.set_enable_write_console_messages_to_stdout(False)

        self.view.connect("decide-policy", self.on_decide_policy)
        self.view.connect("create", self.on_create)
        self.view.connect("ready-to-show", lambda v: self.show_all())
        self.view.connect("close", lambda v: self.destroy())
        self.view.connect("permission-request", self.on_permission)
        self.view.connect("notify::title", self.on_title)
        self.view.connect("load-changed", lambda *a: self.update_buttons())
        self.view.connect("notify::uri", lambda *a: self.update_buttons())
        self.view.connect("web-process-terminated", lambda v, r: v.reload())
        self.connect("key-press-event", self.on_key)

        self.build_ui()

    def build_ui(self):
        header = Gtk.HeaderBar(show_close_button=True, title="Canvas")
        self.back = self.icon_button("go-previous-symbolic", "Back (Alt+Left)", lambda b: self.view.go_back())
        self.fwd = self.icon_button("go-next-symbolic", "Forward (Alt+Right)", lambda b: self.view.go_forward())
        home = self.icon_button("go-home-symbolic", "Dashboard (Alt+Home)", lambda b: self.go_home())
        reload = self.icon_button("view-refresh-symbolic", "Reload (Ctrl+R)", lambda b: self.view.reload())
        for w in (self.back, self.fwd, home, reload):
            header.pack_start(w)
        # Only shown on an assignment page: submits a file written in Omawrite.
        self.turn_in = Gtk.Button(label="Turn in writing", no_show_all=True)
        self.turn_in.get_style_context().add_class("suggested-action")
        self.turn_in.set_tooltip_text("Turn in a file you wrote in Omawrite")
        self.turn_in.connect("clicked", lambda b: self.start_turn_in())
        header.pack_end(self.turn_in)
        self.set_titlebar(header)
        self.header = header

        self.notice = Gtk.InfoBar(message_type=Gtk.MessageType.INFO, show_close_button=True, revealed=False)
        self.notice_label = Gtk.Label(xalign=0)
        self.notice.get_content_area().add(self.notice_label)
        self.notice.connect("response", lambda bar, r: bar.set_revealed(False))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(self.notice, False, False, 0)
        box.pack_start(self.view, True, True, 0)
        self.add(box)
        self.update_buttons()

    def icon_button(self, icon, tip, handler):
        b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
        b.set_tooltip_text(tip)
        b.connect("clicked", handler)
        return b

    def go_home(self):
        self.view.load_uri(self.app.cfg["canvas_url"])

    def update_buttons(self):
        self.back.set_sensitive(self.view.can_go_back())
        self.fwd.set_sensitive(self.view.can_go_forward())
        self.turn_in.set_visible(bool(self.assignment()))

    def assignment(self):
        return turnin.assignment_ids(self.view.get_uri(), urlparse(self.app.cfg["canvas_url"]).hostname)

    def start_turn_in(self):
        ids = self.assignment()
        if ids:
            turnin.TurnIn(self, *ids)

    def on_title(self, view, _):
        self.header.set_title(view.get_title() or "Canvas")

    def show_notice(self, text):
        self.notice_label.set_text(text)
        self.notice.set_revealed(True)
        GLib.timeout_add_seconds(5, lambda: self.notice.set_revealed(False) and False)

    def blocked(self, uri):
        host = urlparse(uri).hostname or uri
        self.show_notice(f"{host} isn't available in Canvas. Ask your teacher if you need it.")

    def on_decide_policy(self, view, decision, kind):
        allowed = self.app.cfg["allowed_hosts"]
        if kind == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            action = decision.get_navigation_action()
            uri = action.get_request().get_uri()
            if is_web(uri) and not host_matches(uri, allowed + self.app.cfg["embed_hosts"]):
                decision.ignore()
                if action.is_user_gesture():
                    self.blocked(uri)
                return True
        elif kind == WebKit2.PolicyDecisionType.RESPONSE:
            uri = decision.get_request().get_uri()
            # Embed hosts (e.g. YouTube) may show inside a frame, never as the whole page.
            if decision.is_main_frame_main_resource() and is_web(uri) and not host_matches(uri, allowed):
                decision.ignore()
                self.blocked(uri)
                return True
            if not decision.is_mime_type_supported():
                decision.download()
                return True
        return False

    def on_create(self, view, action):
        uri = action.get_request().get_uri()
        if uri and is_web(uri) and not host_matches(uri, self.app.cfg["allowed_hosts"]):
            self.blocked(uri)
            return None
        # New tabs and sign-in popups open as another locked-down window.
        return CanvasWindow(self.app, related=view).view

    def on_permission(self, view, request):
        # Camera/mic (Canvas Studio, conferences) and notifications are allowed;
        # location and everything else are denied.
        if isinstance(request, (WebKit2.UserMediaPermissionRequest, WebKit2.NotificationPermissionRequest)):
            request.allow()
        else:
            request.deny()
        return True

    def on_key(self, win, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        alt = event.state & Gdk.ModifierType.MOD1_MASK
        key = Gdk.keyval_name(event.keyval)
        v = self.view
        actions = {
            (alt, "Left"): v.go_back,
            (alt, "Right"): v.go_forward,
            (alt, "Home"): self.go_home,
            (ctrl, "r"): v.reload,
            (True, "F5"): v.reload,
            (ctrl, "equal"): lambda: v.set_zoom_level(v.get_zoom_level() + 0.1),
            (ctrl, "plus"): lambda: v.set_zoom_level(v.get_zoom_level() + 0.1),
            (ctrl, "minus"): lambda: v.set_zoom_level(max(0.3, v.get_zoom_level() - 0.1)),
            (ctrl, "0"): lambda: v.set_zoom_level(1.0),
            (ctrl, "w"): self.close,
        }
        for (mod, name), fn in actions.items():
            if mod and key == name:
                fn()
                return True
        return False


class OmaCanvas(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.cfg = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.cfg = load_config()

        manager = WebKit2.WebsiteDataManager(base_data_directory=DATA_DIR, base_cache_directory=CACHE_DIR)
        self.context = WebKit2.WebContext.new_with_website_data_manager(manager)
        self.context.get_cookie_manager().set_persistent_storage(
            os.path.join(DATA_DIR, "cookies.sqlite"), WebKit2.CookiePersistentStorage.SQLITE)
        self.context.connect("download-started", self.on_download)
        self.content = WebKit2.UserContentManager()

    def do_activate(self):
        if self.get_windows():
            self.get_windows()[0].present()
            return
        win = CanvasWindow(self)
        win.show_all()
        # Nothing loads until the site blocker is in place: fail closed.
        hosts = self.cfg["allowed_hosts"] + self.cfg["embed_hosts"]
        store = WebKit2.UserContentFilterStore.new(os.path.join(CACHE_DIR, "filters"))
        rules = GLib.Bytes.new(content_filter_rules(hosts).encode())
        store.save("allowlist", rules, None, self.on_filter_ready, win)

    def on_filter_ready(self, store, result, win):
        try:
            self.content.add_filter(store.save_finish(result))
        except GLib.Error as e:
            win.show_notice(f"Couldn't start safely ({e.message}). Please tell your teacher.")
            return
        win.go_home()

    def on_download(self, context, download):
        def destination(dl, name):
            folder = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or GLib.get_home_dir()
            base, ext = os.path.splitext(os.path.basename(name) or "download")
            path, n = os.path.join(folder, base + ext), 1
            while os.path.exists(path):
                path, n = os.path.join(folder, f"{base} ({n}){ext}"), n + 1
            dl.set_destination(GLib.filename_to_uri(path))
            return True

        def finished(dl):
            path = GLib.filename_from_uri(dl.get_destination())[0]
            for win in self.get_windows():
                win.show_notice(f"Saved to {path}")
                break

        download.connect("decide-destination", destination)
        download.connect("finished", finished)


if __name__ == "__main__":
    GLib.set_prgname(APP_ID)  # Wayland app id, matches the .desktop file
    sys.exit(OmaCanvas().run(sys.argv))
