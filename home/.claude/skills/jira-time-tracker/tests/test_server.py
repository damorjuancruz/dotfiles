import http.server
import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

import scripts.server as S
from scripts.lib import common


class TestServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "review.html").write_text('<html><body>v1<script id="jtt-data">{}</script></body></html>')
        self.app = S.App(self.dir, "tok")
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S.make_handler(self.app))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        common.write_json(self.dir / S.INFO, {"port": self.port, "token": "tok", "pid": S.os.getpid()})

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def req(self, path, method="GET", body=None, token="tok"):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-JTT-Token"] = token
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        with urllib.request.urlopen(r, timeout=5) as res:
            return res.status, res.read().decode()

    def log_lines(self):
        return (self.dir / S.LOG).read_text().splitlines() if (self.dir / S.LOG).exists() else []

    def test_token_required(self):
        for path in ("/", "/api/state"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.req(path, token=None)
            self.assertEqual(cm.exception.code, 403)
            cm.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.req("/api/state", "PUT", {"round": 1}, token="otro")
        self.assertEqual(cm.exception.code, 403)
        cm.exception.close()

    def test_page_injects_build(self):
        _, html = self.req("/?t=tok", token=None)
        self.assertIn(f'window.JTT_BUILD = "{S.page_build(self.dir)}"', html)
        self.assertLess(html.index("JTT_BUILD"), html.index('id="jtt-data"'))

    def test_state_roundtrip_and_send(self):
        self.assertEqual(self.req("/api/state")[1], "null")
        self.req("/api/state", "PUT", {"round": 1, "levels": {"b2": "breve"}})
        self.assertEqual(json.loads(self.req("/api/state")[1])["levels"], {"b2": "breve"})
        self.assertEqual(self.log_lines(), [])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.req("/api/send", "POST", {"round": 1, "action": "load"})  # falta sent
        cm.exception.close()
        self.req("/api/send", "POST", {"round": 1, "action": "load", "sent": True})
        self.assertTrue(common.read_json(self.dir / S.PAGE_STATE)["sent"])
        self.assertRegex(self.log_lines()[-1], r"^\d\d:\d\d:\d\d ENVIADO ronda=1 acción=load$")

    def test_ask_reply(self):
        _, out = self.req("/api/ask", "POST", {"kind": "comment", "issue": "SUP-1", "prompt": "Redactá…"})
        ask_id = json.loads(out)["id"]
        self.assertEqual(ask_id, "a1")
        self.assertIn("PEDIDO a1 comentario SUP-1", self.log_lines()[-1])
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(S.cmd_ask(self.dir, "a1"), 0)
        self.assertIn("Redactá…", buf.getvalue())
        seq = self.app.seq
        with redirect_stdout(io.StringIO()):
            self.assertEqual(S.cmd_reply(self.dir, "a1", "  Se corrigió.\n"), 0)
            self.assertEqual(S.cmd_reply(self.dir, "a9", "x"), 1)
        self.assertEqual(self.app.events[-1][1:], ("reply", {"id": "a1", "issue": "SUP-1", "text": "Se corrigió."}))
        self.assertGreater(self.app.seq, seq)
        asks = json.loads(self.req("/api/asks")[1])
        self.assertEqual(asks[0]["reply"], "Se corrigió.")

    def test_reload_event_on_page_change(self):
        t = threading.Thread(target=self.app.watch_page, daemon=True)
        t.start()
        time.sleep(0.1)
        seq = self.app.seq
        page = self.dir / "review.html"
        page.write_text("<html><head></head><body>v2</body></html>")
        deadline = time.time() + 3
        while self.app.seq == seq and time.time() < deadline:
            time.sleep(0.1)
        self.assertEqual(self.app.events[-1][1], "reload")

    def test_sse_stream(self):
        r = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/events?t=tok", timeout=5)
        self.assertTrue(r.readline().startswith(b"retry:"))
        self.assertEqual(r.readline().strip(), b"event: hello")
        r.readline(), r.readline()
        self.app.publish("reply", {"id": "a1"})
        self.assertEqual(r.readline().strip(), b"event: reply")
        self.assertEqual(json.loads(r.readline().split(b":", 1)[1]), {"id": "a1"})
        r.close()

    def test_follow_keeps_offset(self):
        S.log_event(self.dir, "INICIADO http://x")
        S.log_event(self.dir, "ENVIADO ronda=1 acción=review")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(S.follow(self.dir, once=True), 0)
        self.assertEqual(len(buf.getvalue().splitlines()), 1)
        self.assertIn("ENVIADO ronda=1", buf.getvalue())
        # Lo ya mostrado no se repite; el evento siguiente sí sale.
        S.log_event(self.dir, "PEDIDO a1 comentario SUP-1")
        buf = io.StringIO()
        with redirect_stdout(buf):
            S.follow(self.dir, once=True)
        self.assertEqual(buf.getvalue().split(" ", 1)[1].strip(), "PEDIDO a1 comentario SUP-1")

    def test_follow_reports_stopped_server(self):
        (self.dir / S.INFO).unlink()
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(S.follow(self.dir, once=False), 1)
        self.assertIn("SERVIDOR DETENIDO", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
