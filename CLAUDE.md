# omacanvas

Locked-down Canvas app (Python, GTK3, WebKit2GTK 4.1) for the student Omarchy fork. Part of the
school dev platform initiative (see `~/.claude/CLAUDE.md`). Fizzy: PacOS board, card #41.

- `omacanvas.py` (window + blocking), `turnin.py` (Omawrite → assignment submission via the
  Canvas API inside the signed-in page). Config: `config.json` (dev) / `/etc/omacanvas/config.json` (installed, wins).
- Never add a URL bar, env/flag config override, or dev tools. That's the whole point.
- New sites go in the config, not code. Keep the content blocker and the navigation policy in sync.
- Pin `Gdk` to 3.0 before importing: something on this system preloads Gdk 4.

## Status
- 0.1.0 works on seno's machine: logs in, blocks off-list pages and iframes (tested).
- Canvas URL is `pacificachristian.instructure.com`. Students sign in with a Canvas username and password (no SSO).
- Turn in writing: plumbing tested, but a real submission hasn't been tested yet (needs a test student
  account and assignment).
- Direction: teacher tools are being rebuilt natively, not as LTI tools, so the allowlist stays short.
