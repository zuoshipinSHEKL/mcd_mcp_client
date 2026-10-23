# -*- coding: utf-8 -*-
"""验证徽章信息是否内嵌在 query-my-account / campaign-calendar 返回中"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://mcp.mcd.cn/mcp-servers/mcd-mcp"
TOKEN = os.environ.get("MCD_MCP_TOKEN", "").strip()
if not TOKEN:
    MCP_JSON = os.path.expanduser("~/.workbuddy/mcp.json")
    with open(MCP_JSON, encoding="utf-8") as f:
        cfg = json.load(f)
    auth = cfg["mcpServers"]["mcd-mcp"]["headers"]["Authorization"]
    TOKEN = auth.split(" ", 1)[1].strip()

session_id = None


def post(body, expect_response=True):
    global session_id
    headers = {
        "Authorization": "Bearer " + TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        print("HTTP %s 错误:" % e.code)
        print(e.read().decode("utf-8", "replace"))
        sys.exit(1)
    sid = resp.headers.get("Mcp-Session-Id")
    if sid:
        session_id = sid
    if not expect_response:
        return None
    raw = resp.read().decode("utf-8", "replace").strip()
    if raw.startswith("data:") or raw.startswith("event:"):
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return None
    if not raw:
        return None
    return json.loads(raw)


def call_tool(rid, name, args=None):
    r = post({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
              "params": {"name": name, "arguments": args or {}}})
    print("=" * 10, name, "=" * 10)
    if r is None:
        print("(无响应)")
        return ""
    if "error" in r:
        print("RPC 错误:", json.dumps(r["error"], ensure_ascii=False))
        return ""
    result = r.get("result", {})
    text = ""
    for item in result.get("content", []):
        if item.get("type") == "text":
            text += item.get("text", "")
    if not text:
        text = json.dumps(result, ensure_ascii=False)
    print(text[:3000])
    print()
    return text


post({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "workbuddy-mcd-probe", "version": "1.0.0"},
    },
})
post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_response=False)

t1 = call_tool(2, "query-my-account")
t2 = call_tool(3, "campaign-calendar")

print("=" * 10, "徽章关键字扫描", "=" * 10)
kw = ["徽章", "badge", "成就", "勋章"]
for label, text in [("query-my-account", t1), ("campaign-calendar", t2)]:
    hits = [k for k in kw if k in text]
    print("%s: %s" % (label, "发现关键字 " + str(hits) if hits else "未发现徽章相关内容"))
