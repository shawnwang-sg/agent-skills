"""paper-vault 本地服务：打开论文库首页，并把首页分类树的编辑保存到 folders.json。

用法（在 vault 目录里）：python serve.py [--port 8791] [--no-browser]
只监听 127.0.0.1，零依赖。
"""
import argparse
import json
import os
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDERS = ROOT / "folders.json"
MAX_BODY = 4 * 1024 * 1024


def valid_tree(nodes, depth=0):
    if not isinstance(nodes, list) or depth > 20:
        return False
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not isinstance(n.get("name"), str):
            return False
        if not all(isinstance(s, str) for s in n.get("papers", [])):
            return False
        if not valid_tree(n.get("children", []), depth + 1):
            return False
    return True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def reply(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/folders":
            return self.reply(404, {"error": "not found"})
        # 只接受本页发来的请求（同源 + JSON），挡住别的网页跨站写入
        origin = self.headers.get("Origin")
        if origin and origin.split("//", 1)[-1] != self.headers.get("Host"):
            return self.reply(403, {"error": "cross-origin"})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self.reply(415, {"error": "json only"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self.reply(413, {"error": "bad size"})
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return self.reply(400, {"error": "bad json"})
        if not isinstance(data, dict) or not valid_tree(data.get("tree")):
            return self.reply(400, {"error": "bad tree"})
        out = {"version": 1, "tree": data["tree"]}
        tmp = FOLDERS.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if FOLDERS.exists():
            os.replace(FOLDERS, FOLDERS.with_suffix(".json.bak"))
        os.replace(tmp, FOLDERS)
        return self.reply(200, {"ok": True})

    def log_message(self, fmt, *args):
        if self.command == "POST":
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description="paper-vault 本地服务")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d/index.html" % a.port
    print("paper-vault: %s  (Ctrl+C 退出)" % url)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
