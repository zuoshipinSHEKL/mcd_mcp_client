# -*- coding: utf-8 -*-
"""麦当劳 MCP 客户端

功能：
  1. 优惠券：查询可领优惠券 -> 一键全部领取 -> 查看我的优惠券
  2. 徽章上线监控：拉取当月活动日历，筛选徽章相关活动，与本地快照对比，
     发现新上线时输出提醒（快照文件 badge_snapshot.json 自动维护）

用法：
  python mcd_mcp_client.py             # 领券 + 徽章监控（默认）
  python mcd_mcp_client.py --coupons   # 仅优惠券流程
  python mcd_mcp_client.py --badge     # 仅徽章上线监控

Token 获取优先级：环境变量 MCD_MCP_TOKEN > ~/.workbuddy/mcp.json 中的 mcd-mcp 配置
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = "https://mcp.mcd.cn/mcp-servers/mcd-mcp"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_FILE = os.path.join(SCRIPT_DIR, "badge_snapshot.json")
BADGE_KEYWORDS = ["徽章", "badge"]  # 徽章相关活动的匹配关键字，可自行扩充


def load_token():
    token = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if token:
        return token
    mcp_json = os.path.expanduser("~/.workbuddy/mcp.json")
    with open(mcp_json, encoding="utf-8") as f:
        cfg = json.load(f)
    auth = cfg["mcpServers"]["mcd-mcp"]["headers"]["Authorization"]
    return auth.split(" ", 1)[1].strip()


TOKEN = load_token()
session_id = None


def post(body, expect_response=True):
    """向 MCP Server 发送 JSON-RPC 请求（Streamable HTTP，兼容 SSE 响应）"""
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
        print("HTTP %s 错误: %s" % (e.code, e.read().decode("utf-8", "replace")))
        sys.exit(1)
    except urllib.error.URLError as e:
        print("网络错误: %s" % e)
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
    return json.loads(raw) if raw else None


def initialize():
    post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "workbuddy-mcd-client", "version": "1.1.0"},
        },
    })
    post({"jsonrpc": "2.0", "method": "notifications/initialized"},
         expect_response=False)


def call_tool(rid, name, args=None):
    """调用 MCP 工具，返回文本结果（失败时返回错误描述）"""
    r = post({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
              "params": {"name": name, "arguments": args or {}}})
    if r is None:
        return "工具 %s 调用失败: 无响应" % name
    if "error" in r:
        return "工具 %s 调用失败: %s" % (name, json.dumps(r["error"], ensure_ascii=False))
    result = r.get("result", {})
    if result.get("isError"):
        return "工具 %s 返回错误" % name
    texts = [item.get("text", "") for item in result.get("content", [])
             if item.get("type") == "text"]
    return "\n".join(texts) if texts else json.dumps(result, ensure_ascii=False)


def run_coupons():
    print("=" * 10, "可领取的优惠券", "=" * 10)
    print(call_tool(10, "available-coupons"))
    print()
    print("=" * 10, "一键领券结果", "=" * 10)
    print(call_tool(11, "auto-bind-coupons"))
    print()
    print("=" * 10, "我的优惠券(领取后)", "=" * 10)
    print(call_tool(12, "query-my-coupons"))


# -------------------- 徽章上线监控 --------------------

def parse_calendar(text):
    """解析活动日历，返回 [{date, status, title, content}, ...]"""
    activities = []
    cur_date = cur_status = None
    cur = None
    in_content = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        m = re.match(r"^####\s*(\d{4}年\d{1,2}月\d{1,2}日)\s*(.*)$", line)
        if m:
            cur_date, cur_status = m.group(1), m.group(2).strip()
            in_content = False
            continue
        if line.startswith("#"):
            in_content = False
            continue
        m = re.match(r"^-\s*\*\*活动标题\*\*：(.+)$", line)
        if m:
            if cur:
                activities.append(cur)
            cur = {"date": cur_date, "status": cur_status,
                   "title": m.group(1).strip(), "content": ""}
            in_content = False
            continue
        if cur is None:
            continue
        if line.startswith("**活动内容介绍**"):
            cur["content"] += re.sub(r"^\*\*活动内容介绍\*\*：?", "", line)
            in_content = True
            continue
        if line.startswith("**") or line.startswith("<img"):
            in_content = False
            continue
        if not line:
            continue
        if in_content:
            cur["content"] += line
    if cur:
        activities.append(cur)
    return activities


def badge_match(a):
    """判断活动是否与徽章相关：title=标题命中, content=内容提及, None=不相关"""
    if any(k in a["title"] for k in BADGE_KEYWORDS):
        return "title"
    if any(k in a["content"] for k in BADGE_KEYWORDS):
        return "content"
    return None


def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"badges": {}}


def save_snapshot(snap):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)


def run_badge_check():
    print("=" * 10, "徽章上线监控", "=" * 10)
    text = call_tool(20, "campaign-calendar")
    if text.startswith("工具 "):
        print(text)
        return
    acts = []
    for a in parse_calendar(text):
        kind = badge_match(a)
        if kind:
            a["match"] = kind
            acts.append(a)
    first_run = not os.path.exists(SNAPSHOT_FILE)
    snap = load_snapshot()
    seen = snap.get("badges", {})
    # 日历中同一活动会跨天重复出现，按 标题+内容前缀 去重，保留首次出现
    unique = {}
    for a in acts:
        key = a["title"] + " :: " + re.sub(r"\s+", "", a["content"])[:30]
        if key not in unique:
            unique[key] = a
    new_keys = [k for k in unique if k not in seen]
    now = datetime.now().isoformat(timespec="seconds")
    for k in new_keys:
        a = unique[k]
        seen[k] = {"first_seen": now, "date": a["date"], "status": a["status"],
                   "title": a["title"], "match": a["match"],
                   "content": a["content"][:200]}
    snap["updated_at"] = now
    save_snapshot(snap)

    if not unique:
        print("当月活动日历中未发现徽章相关活动")
        return
    if first_run:
        print("首次运行，已建立监控基线，当前徽章相关活动 %d 个：" % len(unique))
    else:
        print("徽章相关活动 %d 个，其中新上线 %d 个：" % (len(unique), len(new_keys)))
    for k, a in unique.items():
        kind = "徽章活动" if a["match"] == "title" else "相关提及"
        tag = "【新上线】" if (k in new_keys and not first_run) else "【已知】"
        print()
        print("%s【%s】%s" % (tag, kind, a["title"]))
        print("   日期：%s %s" % (a["date"] or "未知", a["status"] or ""))
        print("   内容：%s" % re.sub(r"\s+", " ", a["content"]).strip()[:120])
    if new_keys and not first_run:
        print()
        print(">>> 徽章上线提醒：" + "；".join(unique[k]["title"] for k in new_keys))


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "all").lstrip("-").lower()
    if mode not in ("all", "coupons", "badge"):
        print("用法: python mcd_mcp_client.py [--coupons|--badge]，不带参数则全部执行")
        sys.exit(1)
    initialize()
    if mode in ("all", "coupons"):
        run_coupons()
    if mode in ("all", "badge"):
        print()
        run_badge_check()


if __name__ == "__main__":
    main()
