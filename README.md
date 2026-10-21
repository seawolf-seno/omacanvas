# OmaCanvas

A Canvas window for Omarchy with no address bar. It can't be used as a general browser.

- Opens only the school's Canvas plus the hosts in the config. Any other site, as a page, a
  new window, or an iframe, is blocked with a short notice.
- Some hosts (YouTube, Google Docs) are allowed only as embeds inside Canvas, never as a
  whole page.
- **Turn in writing:** on an assignment page, students click **Turn in writing**, pick a file
  they saved in Omawrite, and confirm. It goes in as formatted text, or as a `.md` upload if
  the assignment only takes files. This uses the student's own session, so no developer key
  is needed.
- Sign-in, cookies and downloads (to `~/Downloads`) work. Camera and mic are allowed (for
  Canvas Studio). Location and dev tools are off.

## Run

```sh
./omacanvas.py                 # dev: uses ./config.json
make pkg && sudo pacman -U omacanvas-*.pkg.tar.zst   # install as "Canvas" in the launcher
```

Needs `python-gobject`, `gtk3`, `webkit2gtk-4.1` (already on Omarchy) and `python-markdown`.
Without `python-markdown`, turned-in writing loses its formatting.

## Configure

The installed config is `/etc/omacanvas/config.json` (root-owned). When it exists it always
wins, and students can't override it.

| Key | Meaning |
|---|---|
| `canvas_url` | Home page. Its host is always allowed. |
| `allowed_hosts` | Hosts (and their subdomains) that can open as a page: SSO and Canvas services. |
| `embed_hosts` | Hosts that may load only inside a frame on an allowed page. |

When a teacher adds an LTI tool, add its host to `allowed_hosts`, or it shows up blank.

## How blocking works

Two layers, so one gap doesn't open the other:
1. A WebKit content blocker stops any page or frame from loading off the list. The app loads
   nothing until the blocker is in place, so if it fails, the app fails closed.
2. A navigation policy stops whole-page loads and new windows to anything outside
   `allowed_hosts`, and tells the student why.

This app only replaces the browser. The student image also has to drop Chromium and the
Omarchy web-app launchers, which use Chromium.
