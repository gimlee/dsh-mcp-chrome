#!/usr/bin/env bash
# 切换 DSH 常驻浏览器 MCP 插件（管理 ~/.dsh/cordis.patch.yml，保存即热生效）
#
#  on      启用：DSH 独占 bridge（mcp__chrome__* 工具常驻）
#  off     禁用：释放 bridge 给其他客户端（如 zcode）
#  repair  修复：仅重置 bridge（清幽灵会话）。插件配置为无限重连，
#          重启 dsh 后跑一次 repair 即可自动恢复，无需 off/on。
#  status  查看当前状态
#
# 注意：MCP SDK 的 streamable-http close() 不会通知服务端释放会话，
# 所以 on/off/repair 都会顺手重置 bridge（fuser -k 12306/tcp），
# 扩展会在几秒内自动拉起新 host：
#   - on/repair: DSH 插件重连后立即接管
#   - off:       bridge 空闲，下一个连接的客户端(如 zcode)接管
set -e
TARGET="$HOME/.dsh/cordis.patch.yml"
PORT="${DSH_MCP_CHROME_PORT:-12306}"

case "${1:-status}" in
  on)
    cat > "$TARGET" <<'EOF'
# Home-level patch layer — applies to EVERY profile on this machine.
# 常驻浏览器 MCP 工具（hangwin/mcp-chrome bridge）: mcp__chrome__<rawName>
# reconnect.maxAttempts 设大：bridge 出现幽灵会话(如 dsh 重启后)时插件无限重试，
# 只需运行 toggle.sh repair 清掉幽灵即可自动恢复，无需 off/on 循环。
- insert:
    - id: mcp-chrome
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: chrome
        transport: streamable-http
        url: http://127.0.0.1:12306/mcp
        toolCallTimeoutMs: 120000
        reconnect:
          maxAttempts: 1000000
EOF
    echo "mcp-chrome: 已启用（热加载中）"
    fuser -k "$PORT/tcp" 2>/dev/null && echo "bridge 已重置，等待扩展重连…" || true
    echo "DSH 插件将自动重连并接管 bridge。";;
  off)
    printf '# Home-level patch layer (mcp-chrome disabled)\n[]\n' > "$TARGET"
    echo "mcp-chrome: 已禁用"
    fuser -k "$PORT/tcp" 2>/dev/null && echo "bridge 已重置，等待扩展重连…" || true
    echo "bridge 已释放给其他客户端（如 zcode）。";;
  repair)
    echo "repair: 重置 bridge 清幽灵会话…"
    fuser -k "$PORT/tcp" 2>/dev/null && echo "bridge 已重置，等待扩展重连…" || true
    echo "插件为无限重连配置，重连后自动接管。";;
  status)
    if grep -q "id: mcp-chrome" "$TARGET" 2>/dev/null; then
      echo "mcp-chrome: ON"
    else
      echo "mcp-chrome: OFF"
    fi;;
  *)
    echo "用法: $0 <on|off|repair|status>"; exit 1;;
esac
