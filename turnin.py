"""Turn in an Omawrite (Markdown) file to the Canvas assignment that's open.

Calls the Canvas API from inside the signed-in page, so it uses the student's
own session. No developer key or admin setup needed.
"""

import html
import json
import os
import re
import sys
from urllib.parse import urlparse

from gi.repository import GLib, Gtk

try:
    import markdown
except ImportError:  # python-markdown missing: fall back to plain paragraphs
    markdown = None

ASSIGNMENT_PATH = re.compile(r"^/courses/(\d+)/assignments/(\d+)")

# Runs in the page. `action` is "info" or "submit"; returns a JSON string.
JS = r"""
const csrf = decodeURIComponent((document.cookie.match(/(?:^|; )_csrf_token=([^;]+)/) || [])[1] || "");
const api = async (method, path, body) => {
  const r = await fetch(path, {method, credentials: "same-origin", body: body && JSON.stringify(body),
    headers: {"Content-Type": "application/json", "Accept": "application/json", "X-CSRF-Token": csrf}});
  const text = (await r.text()).replace(/^while\(1\);/, "");
  if (!r.ok) throw new Error(r.status + " " + text.slice(0, 200));
  return JSON.parse(text);
};
const base = `/api/v1/courses/${course}/assignments/${assignment}`;
if (action === "info") return JSON.stringify(await api("GET", base));
if (mode === "online_text_entry") {
  await api("POST", base + "/submissions", {submission: {submission_type: mode, body: content}});
} else {
  const blob = new Blob([content], {type: "text/markdown"});
  const pre = await api("POST", base + "/submissions/self/files", {name, size: blob.size, content_type: "text/markdown"});
  const form = new FormData();
  for (const [k, v] of Object.entries(pre.upload_params)) form.append(k, v);
  form.append("file", blob, name);
  const up = await fetch(pre.upload_url, {method: "POST", body: form});
  if (!up.ok) throw new Error("upload " + up.status);
  const file = await up.json();
  await api("POST", base + "/submissions", {submission: {submission_type: mode, file_ids: [file.id]}});
}
return "{}";
"""


def assignment_ids(uri, canvas_host):
    parsed = urlparse(uri or "")
    match = ASSIGNMENT_PATH.match(parsed.path)
    return match.groups() if match and parsed.hostname == canvas_host else None


def to_html(text):
    if markdown:
        return markdown.markdown(text, extensions=["extra", "sane_lists"])
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in text.split("\n\n") if p.strip())


class TurnIn:
    """One turn-in attempt: look up the assignment, pick a file, confirm, submit."""

    def __init__(self, win, course, assignment):
        self.win, self.course, self.assignment = win, course, assignment
        self.call("info", {}, self.on_info)

    def call(self, action, extra, done):
        args = {"action": action, "course": self.course, "assignment": self.assignment, **extra}
        variant = GLib.Variant("a{sv}", {k: GLib.Variant("s", v) for k, v in args.items()})

        def finish(view, result):
            try:
                done(json.loads(view.call_async_javascript_function_finish(result).to_string()))
            except GLib.Error as e:
                print("turn-in failed:", e.message, file=sys.stderr)
                self.win.show_notice("That didn't go through. Check you're signed in and try again, or tell your teacher.")

        self.win.view.call_async_javascript_function(JS, -1, variant, None, None, None, finish)

    def on_info(self, info):
        types = info.get("submission_types", [])
        if "online_text_entry" in types:
            self.mode = "online_text_entry"
        elif "online_upload" in types and self.allows_markdown(info):
            self.mode = "online_upload"
        else:
            self.win.show_notice("This assignment doesn't take written work from Omawrite.")
            return
        if info.get("locked_for_user"):
            self.win.show_notice("This assignment is locked.")
            return
        self.name = info.get("name", "this assignment")
        self.pick_file()

    @staticmethod
    def allows_markdown(info):
        exts = info.get("allowed_extensions") or []
        return not exts or "md" in exts

    def pick_file(self):
        dialog = Gtk.FileChooserDialog(title="Choose your writing (save it in Omawrite first)",
                                       transient_for=self.win, action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Choose", Gtk.ResponseType.ACCEPT)
        md = Gtk.FileFilter()
        md.set_name("Writing (.md, .txt)")
        for pattern in ("*.md", "*.markdown", "*.txt"):
            md.add_pattern(pattern)
        dialog.add_filter(md)
        docs = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
        if docs and os.path.isdir(docs):
            dialog.set_current_folder(docs)
        path = dialog.get_filename() if dialog.run() == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if path:
            self.confirm(path)

    def confirm(self, path):
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if not text.strip():
            self.win.show_notice("That file is empty. Save your writing in Omawrite first.")
            return
        filename = os.path.basename(path)
        dialog = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.QUESTION,
                                   text=f"Turn in “{filename}”?",
                                   secondary_text=f"For: {self.name}\n{len(text.split())} words")
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Turn in", Gtk.ResponseType.ACCEPT)
        ok = dialog.run() == Gtk.ResponseType.ACCEPT
        dialog.destroy()
        if not ok:
            return
        content = to_html(text) if self.mode == "online_text_entry" else text
        self.win.show_notice("Turning in…")
        self.call("submit", {"mode": self.mode, "content": content, "name": filename}, self.on_submitted)

    def on_submitted(self, _):
        self.win.show_notice(f"Turned in to {self.name}.")
        self.win.view.reload()
