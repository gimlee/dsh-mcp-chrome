# dsh-mcp-chrome

给 DeepSeek Harness（DSH）常驻接入 Chrome 浏览器 MCP 工具：模型直接获得
`mcp__chrome__*` 这一组浏览器能力。

## 这是什么

`mcp-chrome` 是一个 DSH 插件实例，底层复用官方
[`@deepseek-ai/dsh-mcp-client`](https://github.com/gimlee/dsh-mcp-client)
桥接插件，连接本机 [hangwin/mcp-chrome](https://github.com/hangwin/mcp-chrome)
的 streamable-http bridge（默认 `http://127.0.0.1:12306/mcp`）。

```
DSH / 其他 agent
        │
        │  mcp__chrome__chrome_navigate / chrome_javascript / ...
        ▼
@deepseek-ai/dsh-mcp-client  ──streamable-http──▶  mcp-chrome bridge :12306
        ▲                                                    │
        └──────────── mcp-chrome.py / toggle.sh ─────────────┘
```

## 仓库内容

- `cordis.patch.yml`：DSH home 级 patch，插入 `mcp-chrome` 插件实例。
- `mcp-chrome.py`：命令行薄封装，让任何 agent 用一条命令调用 bridge。
- `dsh-mcp-chrome-toggle.sh`：`on / off / repair / status` 一键切换插件，保存即热生效。

## 安装

### 1. 安装并启动 mcp-chrome bridge

```bash
pnpm install -g mcp-chrome-bridge
mcp-chrome-bridge register
```

然后在 Chrome 中安装并连接 mcp-chrome 扩展，扩展会自动拉起 bridge 并监听 `12306`。

### 2. 给 DSH 常驻接入

```bash
cp cordis.patch.yml ~/.dsh/cordis.patch.yml
```

DSH 热加载后，模型即可看到 `mcp__chrome__*` 工具。

也可以直接使用开关脚本：

```bash
./dsh-mcp-chrome-toggle.sh on     # 启用，DSH 独占 bridge
./dsh-mcp-chrome-toggle.sh status # 查看状态
./dsh-mcp-chrome-toggle.sh off    # 禁用，释放 bridge 给 zcode 等客户端
./dsh-mcp-chrome-toggle.sh repair # 重置 bridge，清理幽灵会话
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

- `serverName: chrome` → 模型侧工具名为 `mcp__chrome__<rawName>`
- `reconnect.maxAttempts: 1000000` → bridge 出现幽灵会话时插件持续重试，
  跑一次 `repair` 即可自动恢复，无需反复 off/on

## 给其他 agent 使用

```bash
./mcp-chrome.py ping
./mcp-chrome.py list
./mcp-chrome.py tabs
./mcp-chrome.py js 'return document.title' --tab <tabId>
./mcp-chrome.py nav https://example.com --tab <tabId>
./mcp-chrome.py call chrome_read_page '{"filter":"interactive"}'
```

> 注意：bridge 同一时刻只服务一个 MCP 客户端。DSH 插件启用时会独占；
> 需要给其他 agent 用时先执行 `./dsh-mcp-chrome-toggle.sh off`。

## 社区

本项目认可 [LINUX DO](https://linux.do/) 社区。
