# -*- coding: utf-8 -*-
"""麦当劳 MCP 客户端：查询可领优惠券 -> 一键领取 -> 验证我的优惠券"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://mcp.mcd.cn/mcp-servers/mcd-mcp"

# Token 获取优先级：环境变量 MCD_MCP_TOKEN > MCP 客户端配置文件
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
    except urllib.error.URLError as e:
        print("网络错误:", e)
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


def show(title, r):
    print("=" * 10, title, "=" * 10)
    if r is None:
        print("(无响应体)")
        return
    if "error" in r:
        print("RPC 错误:", json.dumps(r["error"], ensure_ascii=False))
        return
    result = r.get("result", {})
    if "content" in result:
        for item in result["content"]:
            if item.get("type") == "text":
                print(item.get("text", ""))
            else:
                print(json.dumps(item, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


# 1. 初始化
r = post({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "workbuddy-mcd-client", "version": "1.0.0"},
    },
})
show("initialize", r)

# 2. 初始化完成通知
post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_response=False)

# 3. 工具列表
r = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
print("=" * 10, "可用工具", "=" * 10)
for t in r.get("result", {}).get("tools", []):
    print("- %s: %s" % (t.get("name"), (t.get("description") or "").replace("\n", " ")[:70]))

# 4. 查询可领优惠券
r = post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "available-coupons", "arguments": {}}})
show("可领取的优惠券", r)

# 5. 一键领取全部可领优惠券
r = post({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
          "params": {"name": "auto-bind-coupons", "arguments": {}}})
show("一键领券结果", r)

# 6. 验证：我的优惠券
r = post({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
          "params": {"name": "query-my-coupons", "arguments": {}}})
show("我的优惠券(领取后)", r)
