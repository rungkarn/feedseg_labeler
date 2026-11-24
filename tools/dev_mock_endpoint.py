"""Mock Apps Script endpoint for local tests: python tools/dev_mock_endpoint.py [port]  (default 8788).
Stores rows in memory; POST (any path) and GET ?action=dump[&pack=][&user=]; same validation as apps_script.gs."""
import json, re, sys, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROWS = []
USER_RE = re.compile(r"^[\w\u0E00-\u0E7F\-]{1,30}$")
PACK_RE = re.compile(r"^[\w\-]{1,60}$")
IMG_RE = re.compile(r"^[\w.\-]{1,120}$")

class H(BaseHTTPRequestHandler):
    def _send(self, o, code=200):
        b = json.dumps(o).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        user, pack = str(body.get("user")), str(body.get("pack"))
        n = 0
        if USER_RE.match(user) and PACK_RE.match(pack):
            for r in (body.get("rows") or [])[:500]:
                try:
                    cls, aid = int(r["cls"]), int(r["aid"])
                except Exception:
                    continue
                f = str(r.get("flags", ""))
                if not (-1 <= cls <= 6 and aid >= 0 and IMG_RE.match(str(r.get("image_id"))) and re.fullmatch(r"[cxe]{0,3}", f)):
                    continue
                ROWS.append([datetime.datetime.utcnow().isoformat() + "Z", user, pack, r["image_id"], aid, cls, f,
                             r.get("auto", ""), r.get("t", "")])
                n += 1
        self._send({"ok": True, "n": n})

    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if q.get("action") != "dump":
            return self._send({"ok": True, "service": "mock"})
        rows = [r for r in ROWS if (not q.get("pack") or r[2] == q["pack"]) and (not q.get("user") or r[1] == q["user"])]
        self._send({"ok": True, "rows": rows})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
    HTTPServer(("127.0.0.1", port), H).serve_forever()
