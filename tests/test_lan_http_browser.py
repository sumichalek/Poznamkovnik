from __future__ import annotations

import html
from contextlib import ExitStack
import json
import os
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

from backend.api import AppContext, AppHandler


PAGE = """<!doctype html><meta charset="utf-8"><pre id="report">pending</pre>
<script>
(async () => {
  const check = (value, message) => { if (!value) throw new Error(message); };
  const until = async predicate => {
    for (let attempt = 0; attempt < 150; attempt += 1) {
      if (await predicate()) return;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error('Browser condition timed out');
  };
  check(!window.isSecureContext, 'Test must use a non-secure LAN-like HTTP origin');
  const setup = await fetch('/api/auth/setup', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: 'LAN Browser Fixture', password: 'browser-fixture-password-only'})
  });
  check(setup.ok, 'Temporary account setup failed');
  const frame = document.createElement('iframe');
  frame.src = '/';
  const loaded = new Promise(resolve => frame.onload = resolve);
  document.body.append(frame);
  await loaded;
  const app = frame.contentWindow;
  const doc = frame.contentDocument;
  check(!app.isSecureContext, 'Application must really be in a non-secure context');
  check(typeof app.crypto.randomUUID === 'undefined', 'Test must not expose native randomUUID');
  await until(() => doc.getElementById('app-shell')?.hidden === false);
  doc.getElementById('library-create-button').click();
  doc.getElementById('library-name').value = 'Tvorivá knižnica';
  doc.getElementById('library-tags').value = 'tvorba';
  doc.getElementById('library-save-button').click();
  await until(() => doc.querySelector('.library-select')?.textContent === 'Tvorivá knižnica');
  let library;
  await until(async () => {
    const response = await fetch('/api/workspace');
    check(response.ok, 'Workspace request failed');
    const workspace = await response.json();
    library = workspace.libraries.find(item => item.name === 'Tvorivá knižnica');
    return Boolean(library);
  });
  check(library.tags.length === 1 && library.tags[0] === 'tvorba', 'Tag was not persisted');
  check(doc.getElementById('library-form').hidden, 'Form was not closed after saving');
  document.getElementById('report').textContent = JSON.stringify({
    ok: true, secureContext: app.isSecureContext, nativeUUID: typeof app.crypto.randomUUID, id: library.id
  });
})().catch(error => document.getElementById('report').textContent = JSON.stringify({ok: false, error: String(error)}));
</script>"""


class BrowserHandler(AppHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path != "/__lan_test":
            super().do_GET()
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(os.environ.get("POZNAMKOVNIK_BROWSER_TESTS") == "1" and shutil.which("chromium"),
                     "Opt-in real browser check: POZNAMKOVNIK_BROWSER_TESTS=1 and Chromium required")
class LanHttpBrowserTest(unittest.TestCase):
    def test_create_library_in_real_insecure_http_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-lan-browser-") as temporary, ExitStack() as resources:
            root = Path(temporary)
            project = Path(__file__).resolve().parents[1]
            with patch("backend.api.AutomaticBackupScheduler.start"), patch("backend.api.RadioRecordingScheduler.start"), patch("backend.api.CalendarReminderScheduler.start"):
                context = AppContext(project, root / "data")
            resources.callback(context.development_debugger.close)
            resources.callback(context.serial_monitor.close)
            resources.callback(context.language_services.close)
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(BrowserHandler, context=context))
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
            thread.start()
            try:
                # Browser-only mapping to a local fixture, not a system DNS/Pi-hole change.
                # A non-localhost origin exercises real secure-context restrictions.
                result = subprocess.run([
                    shutil.which("chromium"), "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", "--disable-background-networking", "--disable-sync",
                    "--no-proxy-server", "--host-resolver-rules=MAP poznamkovnik.test 127.0.0.1",
                    f"--user-data-dir={root / 'browser-profile'}", "--virtual-time-budget=15000", "--dump-dom",
                    f"http://poznamkovnik.test:{server.server_port}/__lan_test",
                ], capture_output=True, text=True, timeout=45)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result.returncode, 0, result.stderr[-2500:])
            match = re.search(r'<pre id="report">(.*?)</pre>', result.stdout, re.S)
            self.assertIsNotNone(match, result.stdout[-2500:])
            report = json.loads(html.unescape(match[1]))
            self.assertTrue(report.get("ok"), report)
            self.assertFalse(report["secureContext"])
            self.assertEqual(report["nativeUUID"], "undefined")
            self.assertEqual(uuid.UUID(report["id"]).version, 4)
