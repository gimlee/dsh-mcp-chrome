# dsh-mcp-chrome 项目介绍

**dsh-mcp-chrome** 给 DeepSeek Harness 常驻接入 Chrome 浏览器 MCP 工具。

GitHub: https://github.com/gimlee/dsh-mcp-chrome

## 它是什么

一个名为 `mcp-chrome` 的 DSH 插件实例，底层使用官方
`@deepseek-ai/dsh-mcp-client`，连接本机
[hangwin/mcp-chrome](https://github.com/hangwin/mcp-chrome) bridge。
接入后模型直接获得 `mcp__chrome__*` 浏览器工具集。

## 架构

```text
DSH / 其他 agent
   │  mcp__chrome__chrome_navigate / chrome_javascript / ...
   ▼
@deepseek-ai/dsh-mcp-client ──streamable-http──▶ mcp-chrome bridge :12306
   ▲                                      ▲
   └────── mcp-chrome.py / toggle.sh ─────┘
```

## 插件配置

```yaml
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
```

## 快速使用

- `cp cordis.patch.yml ~/.dsh/cordis.patch.yml`，DSH 热加载后工具常驻。
- `dsh-mcp-chrome-toggle.sh on/off/repair/status` 一键切换。
- `mcp-chrome.py list / tabs / js / nav / shot`，给任意 agent 命令行调用。

仓库自带 patch 配置、命令行封装和开关脚本，即拷即用。
本项目认可 [LINUX DO](https://linux.do/) 社区。
