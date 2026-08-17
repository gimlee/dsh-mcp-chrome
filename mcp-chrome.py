#!/usr/bin/env python3
"""
mcp-chrome.py — 薄封装：让任何 agent（含本机 DSH）用一条命令调用
hangwin/mcp-chrome 的浏览器 MCP 工具。

端点: 默认 http://127.0.0.1:12306/mcp（可用环境变量 MCP_CHROME_URL 覆盖）
会话: 缓存在 ~/.cache/mcp-chrome/session，自动握手/自动续

用法:
  mcp-chrome.py ping                      检查 bridge 是否在线
  mcp-chrome.py list                      列出所有工具
  mcp-chrome.py schema <tool>             显示工具的 inputSchema
  mcp-chrome.py call <tool> '<json>'      调用工具, 如:
      mcp-chrome.py call chrome_navigate '{"url":"https://example.com"}'
  mcp-chrome.py tabs                      快捷: 列出窗口/标签
  mcp-chrome.py js '<code>'               快捷: 页面上下文执行 JS [--tab <id>]
  mcp-chrome.py nav <url>                 快捷: 活动标签导航 [--tab <id>]
  mcp-chrome.py shot                      快捷: 活动标签截图
  mcp-chrome.py raw '<jsonrpc-json>'      原样发送一个 JSON-RPC
  mcp-chrome.py close                     释放会话
  mcp-chrome.py reset                     强制重置 bridge(会断开其他客户端)
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("MCP_CHROME_URL", "http://127.0.0.1:12306/mcp")
PING = os.environ.get("MCP_CHROME_PING", "http://127.0.0.1:12306/ping")
CACHE_DIR = os.path.expanduser("~/.cache/mcp-chrome")
SESSION_FILE = os.path.join(CACHE_DIR, "session")
TIMEOUT = int(os.environ.get("MCP_CHROME_TIMEOUT", "45"))


def _http(method, url, payload=None, session=None, extra_headers=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return 0, {}, f"URLError: {e.reason}"


def _parse_sse(body):
    """从 SSE 响应里抽出 JSON-RPC 消息(可能多行 data)。"""
    events = []
    current = None
    for line in body.splitlines():
        if line.startswith("data:"):
            chunk = line[len("data:"):].strip()
            if current is None:
                current = chunk
            else:
                current += "\n" + chunk
        elif line.startswith("event:"):
            pass
        elif line == "" and current is not None:
            events.append(current)
            current = None
    if current is not None:
        events.append(current)
    return events


def _rpc(payload, session=None, expect_session=False):
    """发送 JSON-RPC，返回 (parsed_message, new_session_id)。"""
    status, headers, body = _http("POST", BASE, payload, session)
    if status != 200 and status != 202:
        try:
            err = json.loads(body)
            msg = err.get("message") or err.get("error") or body
        except Exception:
            msg = body
        raise RuntimeError(f"HTTP {status}: {msg}")
    sid = headers.get("mcp-session-id") or (session if expect_session else None)
    msgs = _parse_sse(body)
    if not msgs:
        return None, sid
    parsed = None
    for m in msgs:
        try:
            obj = json.loads(m)
            if obj.get("id") is not None or "error" in obj:
                parsed = obj
        except Exception:
            pass
    return parsed, sid


def _load_session():
    try:
        with open(SESSION_FILE) as f:
            return f.read().strip() or None
    except Exception:
        return None


def _save_session(sid):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        f.write(sid)


def _drop_session():
    try:
        os.remove(SESSION_FILE)
    except Exception:
        pass


def _init():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "mcp-chrome.py", "version": "1.0"},
        },
    }
    msg, sid = _rpc(payload, expect_session=True)
    if sid:
        _save_session(sid)
    # 规范要求客户端在 initialize 后发 initialized 通知(无 id)
    _rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}, session=sid)
    return sid


def _ensure_session():
    sid = _load_session()
    if sid:
        return sid
    return _init()


def _retry_once(fn):
    try:
        return fn()
    except RuntimeError as e:
        if "Invalid MCP request or session" in str(e) or "session" in str(e).lower():
            _drop_session()
            return fn()
        raise


def _call_tool(name, args, tab_id=None):
    if tab_id is not None and "tabId" not in args:
        args = dict(args)
        args["tabId"] = tab_id

    def do():
        sid = _ensure_session()
        rid = int(time.time() * 1000) % 1000000
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        msg, _ = _rpc(payload, session=sid)
        if msg is None:
            return {"error": "empty response"}
        if "error" in msg and "result" not in msg:
            return msg
        return msg

    return _retry_once(do)


def _fmt_result(msg):
    out = []
    if msg.get("error"):
        out.append("ERROR: " + json.dumps(msg["error"], ensure_ascii=False))
        return "\n".join(out)
    result = msg.get("result", {})
    if "content" in result:
        for item in result["content"]:
            if item.get("type") == "text":
                txt = item["text"]
                try:
                    obj = json.loads(txt)
                    out.append(json.dumps(obj, ensure_ascii=False, indent=2))
                except Exception:
                    out.append(txt)
        if result.get("isError"):
            out.append("[isError=true]")
    else:
        out.append(json.dumps(result, ensure_ascii=False, indent=2))
    return "\n".join(out)


def cmd_ping():
    status, _, body = _http("GET", PING)
    print(body or f"HTTP {status}")
    return 0 if status == 200 else 1


def cmd_list():
    def do():
        sid = _ensure_session()
        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        msg, _ = _rpc(payload, session=sid)
        if msg and "result" in msg:
            tools = msg["result"].get("tools", [])
            for t in tools:
                desc = (t.get("description") or "").replace("\n", " ")[:70]
                print(f"- {t['name']}: {desc}")
            print(f"\n共 {len(tools)} 个工具")
            return 0
        print("无响应或失败:", json.dumps(msg, ensure_ascii=False)[:300])
        return 1

    return _retry_once(do)


def cmd_schema(tool):
    def do():
        sid = _ensure_session()
        payload = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        msg, _ = _rpc(payload, session=sid)
        for t in msg["result"].get("tools", []):
            if t["name"] == tool:
                print(json.dumps(t.get("inputSchema", {}), ensure_ascii=False, indent=2))
                return 0
        print(f"工具不存在: {tool}")
        return 1

    return _retry_once(do)


def cmd_call(tool, args_json):
    try:
        args = json.loads(args_json) if args_json.strip() else {}
    except Exception:
        print(f"参数不是合法 JSON: {args_json}")
        return 1
    msg = _call_tool(tool, args)
    print(_fmt_result(msg))
    return 0


def cmd_tabs():
    print(_fmt_result(_call_tool("get_windows_and_tabs", {})))
    return 0


def cmd_js(code, tab_id):
    print(_fmt_result(_call_tool("chrome_javascript", {"code": code}, tab_id)))
    return 0


def cmd_nav(url, tab_id):
    args = {"url": url}
    print(_fmt_result(_call_tool("chrome_navigate", args, tab_id)))
    return 0


def cmd_shot(tab_id):
    print(_fmt_result(_call_tool("chrome_screenshot", {}, tab_id)))
    return 0


def cmd_raw(raw_json):
    payload = json.loads(raw_json)
    sid = _load_session()
    msg, _ = _rpc(payload, session=sid)
    print(json.dumps(msg, ensure_ascii=False, indent=2) if msg else "(no message)")
    return 0


def cmd_close():
    sid = _load_session()
    if sid:
        _http("DELETE", BASE, session=sid)
    _drop_session()
    print("会话已释放")
    return 0


def cmd_reset():
    print("强制重置 bridge（将断开其他 MCP 客户端，如 zcode）...")
    subprocess.run(["fuser", "-k", "12306/tcp"], capture_output=True)
    _drop_session()
    for _ in range(20):  # 等扩展重连拉起服务, 最多 ~20s
        status, _, _ = _http("GET", PING)
        if status == 200:
            print("bridge 已恢复")
            return 0
        time.sleep(1)
    print("等待超时: bridge 未恢复。请在 Chrome 扩展里点 Connect 后重试。")
    return 1


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd = argv[0]
    try:
        if cmd == "ping":
            return cmd_ping()
        if cmd == "list":
            return cmd_list()
        if cmd == "schema":
            return cmd_schema(argv[1])
        if cmd == "call":
            return cmd_call(argv[1], argv[2] if len(argv) > 2 else "{}")
        if cmd == "tabs":
            return cmd_tabs()
        if cmd == "js":
            tab = None
            rest = argv[1:]
            if rest and rest[0] == "--tab":
                tab = int(rest[1])
                rest = rest[2:]
            return cmd_js(rest[0], tab)
        if cmd == "nav":
            tab = None
            rest = argv[1:]
            if rest and rest[0] == "--tab":
                tab = int(rest[1])
                rest = rest[2:]
            return cmd_nav(rest[0], tab)
        if cmd == "shot":
            tab = None
            rest = argv[1:]
            if rest and rest[0] == "--tab":
                tab = int(rest[1])
            return cmd_shot(tab)
        if cmd == "raw":
            return cmd_raw(argv[1])
        if cmd == "close":
            return cmd_close()
        if cmd == "reset":
            return cmd_reset()
        print(f"未知命令: {cmd}")
        return 1
    except RuntimeError as e:
        msg = str(e)
        print(f"失败: {msg}")
        if "Already connected" in msg:
            print("提示: bridge 同一时刻只服务一个 MCP 客户端(如 zcode 正连着)。")
            print("     等它断开后重试, 或用 `reset` 强制重置。")
        if "URLError" in msg or "Connection refused" in msg:
            print("提示: bridge 未在线。检查 Chrome 扩展是否已 Connect。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
