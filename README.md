# Cursor Sand Toolkit

> ## ⚡ 由 [Riot](https://github.com/caiwuu/Riot) 打造。
>
> 本项目由 **Riot —— 跑在你机器上的全能智能体** 逆向与维护。
> Riot 能写代码、调研、排查、自动化，把手头的活真正做完，而不是只给建议。
> 觉得这工具好用？**去给 [Riot](https://github.com/caiwuu/Riot) 点个 Star** ⭐

Cursor 客户端模式管理器 —— 伪装 sand 计费到 bot，并绕过后端封堵。

## 能力一览（`install` 一次全生效）

| 能力              | 说明                                                                                           |
| ----------------- | ---------------------------------------------------------------------------------------------- |
| sand 伪装         | `client-type` → sand，计费到 bot 额度                                                          |
| 会话流（默认）    | 只打标记，复用官方 `runInference`，网页 Usage 记到 bot / free                                  |
| 绕过封堵          | managed-local 本地推理，绕过后端 sand 流量拒绝                                                 |
| 工具执行          | move-exec 强制 ON，恢复 shell/read/glob 工具                                                   |
| 子 agent（Task）  | 本地子 agent，含后台多任务                                                                     |
| 五模式放行        | Agent / Ask / Plan / Debug / Multitask 全走本地；Plan Build（`executePlanAction`）也走本地     |
| 1M 上下文         | maxTokens 覆盖，恢复上下文窗口与压缩                                                           |
| 首字(TTFT)优化    | `buildFromPushedData` 等待 pushed rules 超时 10s → 1s，见下文                                  |
| Rules/Skills 恢复 | move_exec ON 时补调 agent-exec `activate`，恢复 rules/skills 收集推送                          |
| User Rules 注入   | Settings → Rules 里的 User / Team rules 在本地 loop 也进 prompt（原本只有云端链路才有）        |
| MCP 恢复          | `<mcp_file_system>` 提示块不再依赖服务端 flag，agent 重新看得到已连接的 MCP server             |
| Plan 交互修复     | 同一 turn 先 AskQuestion 再 CreatePlan，不再报 `askQuestionInteractionResponse`                |
| DSV3 模型降级     | Composer / Auto / grok-4.6 降级到通用 harness 试跑，不再重试 3 次后报 `dsv31018ToolsGenerator` |

## 前提

- Cursor 版本 **3.18.9**，且必须是 [Releases](https://github.com/caiwuu/sand/releases) 里提供的那份安装包，原因见下
- 账号需已开通 **Sand 资格**（bot 额度）
- 日常建议用 claude 系列模型（grok 偶有额度/行为不稳）

## ⚠️ 必须用本仓库提供的 Cursor 安装包

Cursor 走 CDN 分发，**同一个版本号下可能存在多份构建产物**。这些产物功能一致，但 minify 后的
函数名、变量名不一样——比如首字超时那个常量，3.18.25 叫 `yCd`，3.18.9 叫 `Ykd`。

本工具的每一处补丁都是按这些**混淆后的名字**去精确匹配并替换的。名字对不上时：

- 好一点的情况是锚点匹配不到，`install` 报「未完整匹配 Sand Stream 规则」直接中止，不会改坏；
- 差一点的情况是只匹配上一部分，装出来半残——比如工具能用但 Rules/MCP 不见了。

所以请到 [Releases](https://github.com/caiwuu/sand/releases) 下载**本仓库上传的 3.18.9 安装包**，
不要用官网自动更新或别处下载的 3.18.9。装完记得关掉 Cursor 自动更新，否则一次后台更新就会把
补丁连同整个 bundle 覆盖掉。

## 下载

- **Cursor 3.18.9 安装包**：[Releases](https://github.com/caiwuu/sand/releases)（务必用这份，别用官网的）
- **本工具二进制**：同样在 [Releases](https://github.com/caiwuu/sand/releases) 或 Actions 产物区，按平台选。

## 使用

### Mac

```bash
# 首次运行前去掉隔离标记
xattr -d com.apple.quarantine ./cursor-sand-toolkit

# 安装（弹系统密码框，输 Mac 登录密码）
./cursor-sand-toolkit install
```

### Windows

管理员身份打开 PowerShell：

```powershell
.\cursor-sand-toolkit.exe install
```

SmartScreen 提示时点「更多信息 → 仍要运行」。

### 交互式菜单（可选）

直接双击运行，选 `1` 启用 Stream 模式。

## 其他命令

```bash
./cursor-sand-toolkit install               # 默认会话流（网页 Usage 走 bot）
./cursor-sand-toolkit install --transport direct   # 旧版直连回退
./cursor-sand-toolkit uninstall             # 卸载还原
./cursor-sand-toolkit set-path <Cursor路径>  # 指定安装路径（auto 自动检测）
./cursor-sand-toolkit move-exec-check       # 单独检查工具执行补丁
./cursor-sand-toolkit move-exec-apply       # 单独应用
./cursor-sand-toolkit move-exec-restore     # 单独还原
./cursor-sand-toolkit ttft-check            # 检查首字(TTFT)超时补丁状态
./cursor-sand-toolkit ttft-apply            # 应用首字(TTFT)超时优化（10s → 1s）
./cursor-sand-toolkit ttft-restore          # 还原首字(TTFT)超时优化（只改超时串，不整文件覆盖）
./cursor-sand-toolkit ttft-sync             # 同步 product.json 校验和（修复 corrupt）
./cursor-sand-toolkit rules-skills-check    # 检查 Rules/Skills 恢复补丁状态
```

## 首字(TTFT)延迟优化

Cursor 每轮请求的首字延迟里，有一笔固定开销：`buildFromPushedData` 会等待服务器推送的
rules/文件上下文，若推送未送达则**空等 10 秒**后 fallback。把这段内置超时从 10s 改到 1s，
可把每轮固定开销从 ~12s 压到 ~3s（服务端生成时间另计）。

```bash
./cursor-sand-toolkit ttft-check     # 看当前是 10s 还是已 1s
./cursor-sand-toolkit ttft-apply     # 10s → 1s，并同步 checksum、重启 Cursor
./cursor-sand-toolkit ttft-restore   # 只反向替换超时常量，不整文件覆盖
./cursor-sand-toolkit ttft-sync      # 校验和失配时单独修复 product.json
```

- **纯本地改动**：只改 `out/vs/workbench/workbench.desktop.main.js` 里的一个超时常量，无服务端依赖。
- **还原不会整文件回滚**：`workbench.desktop.main.js` 上还有其它 Sand 补丁，整文件覆盖会把它们一起拆掉。
- **checksum**：改 bundle 后必须同步 `product.json`，否则 Cursor 可能报安装损坏。`install` / `ttft-apply` / `ttft-restore` 会自动同步；若只看到告警，跑 `ttft-sync`。
- **版本差异坑**：minify 后的变量名随构建变——3.18.25 叫 `yCd`，3.18.9 叫 `Ykd`（值均为 `1e4`）。
  工具已同时认这两个名字；若你手上那份构建又换了名字，`ttft-check` 会报「版本不同」。这正是
  [必须用本仓库安装包](#️-必须用本仓库提供的-cursor-安装包)的原因，别的补丁没有这种多名字兜底。
- **更新后重打**：Cursor 自动更新会覆盖 bundle，`ttft-check` 重新显示「未补丁」时重跑一次 `ttft-apply`。

## Rules/Skills 恢复

`cursor-agent-exec` 的 `aa()` 在 `cursorAgentHostEnabled` 时只注册 runtime handle，
**不调用 `na()`**（`activateCursorAgentRuntime`）。Rules/Skills 只有 `na()` 才会
`updateCursorRules` / `updateAgentSkills` 推到 workbench。Sand 打开 agent-host 后
这条链路被跳过，Context Usage 里 Rules / Skills 整类消失（MCP 仍在，因为它走 host 自己的 provider）。

V4 直接改 `aa()`：host 启用时仍 `await na({registerAgentExecProvider:!1})`，并置
`ia=!0` 以便停扩展时走官方 `ra()`。不再从 host 侧 `createLiveExecRuntime` 抢跑
（V1–V3 的 2s 超时经常在 exec 还没 register 时就失败，看起来像「补丁打了但 rules 还是没有」）。

```bash
./cursor-sand-toolkit rules-skills-check    # 看 V4 是否已打上
```

- 锚点仅确认于 Cursor **3.18.9** 的 `extensions/cursor-agent-exec/dist/main.js`。
- `install` 会先剥离 host 侧 V1–V3 旧注入，再打 V4；旧标记剥不干净会拒绝安装。

### Skills 有了，Rules 还是 0？

V4 只解决「推送链路没跑」。Context Usage 里 **Rules** 分类还需要有东西可推：

- **文件规则**（`.cursor/rules/*.mdc`、`~/.cursor/rules`）：V4 之后已经走 `updateCursorRules` 正常推送。
- **User Rules**（Settings → Rules → User Rules，例如「Always respond in 中文」）：属于「非文件规则」，
  云端链路由服务端拼进 prompt；managed-local 本地拼 prompt 时，workbench 的
  `injectLocalModeNonFileRules` 只在 `localMode` 才把它们并进 `requestContext.rules`，
  所以之前 sand 模式下永远进不了 prompt。`1.5.4` 打掉这个守卫（`/*SAND_USER_RULES_V1*/`），
  User / Team rules 现在也会随本地 prompt 一起发出。

## MCP 不见了（Context Usage 里没有「MCP & dynamic tools」）

MCP 本身是连着的：`cursor-agent-exec` 的 MCP FileSystem Writer 会把每个 server 的工具描述写到
`~/.cursor/projects/<项目>/mcps/<server>/`，`CallMcpTool` 也能直接调通。缺的只是 **system prompt 里
那段告诉 agent「去哪找 MCP」的说明**，所以模型根本不知道有哪些 server，Context Usage 里这一类也就是 0。

根因在 `cursor-agent-host/dist/675.js` 的 `O$()`：只有 `mcpMetaToolOptions.enabled`，或
`featureFlags.enableMCPFileSystem` 为真，才会渲染 `<mcp_file_system>`。这个 flag 随会话由服务端下发，
sand / managed-local 拿不到，于是整段提示被跳过。

`1.5.4` 把这个判断固定为真（`/*SAND_MCP_FILESYSTEM_V1*/`）。只要 `mcpFileSystemOptions.enabled` 且
descriptors 非空，提示块就会照常进 prompt——判据本来就来自本地已写好的描述文件，不需要服务端参与。

## Plan 模式：先问再建计划报 `askQuestionInteractionResponse`

`create_plan_v2` 偶发失败：`Unexpected response for create plan query: askQuestionInteractionResponse`。
触发条件是**同一 turn 里先调 AskQuestion、再调 CreatePlan**——Plan 模式的提示词恰恰鼓励先问再建。

根因在 `cursor-agent-host/dist/657.js`：interaction registry 用 `${turnId}:${query.id}` 做 key，
而本地 loop 构造 `InteractionQuery` 时从不填 `id`（uint32，恒为 0）。同一 turn 的第二个交互直接命中
第一个已缓存的应答。官方在 `queryFromChild` / `querySurfacedForSubagent` 里都补了 `seq`，唯独主会话的
`query` 漏了。`1.5.4` 给主会话 `query` 同样加上递增 `seq`（`/*SAND_INTERACTION_SEQ_V1*/`）。

## Composer / Auto / grok-4.6（DSV3 harness）

这几个模型服务端返回 `useDsv3Harness: true`，而 **3.18.9 的本地运行时没有 DSV3 prompt 构造实现**
（`dsv31018ToolsGenerator` 只出现在报错字符串里）。官方在这个版本的行为是直接拒绝：
「uses the Composer (DSV3) prompt path, which the local loop does not construct yet」。

- 从 3.18.25 fork 移植的 V1 只是屏蔽了那个守卫，请求继续往下走，到 `doe()` 里抛
  `Tools for dsv3-1018 are handled in dsv31018ToolsGenerator`，还要重试 3 次（约 20s）才报错。
- `1.5.4` 换成 V2（`/*SAND_DSV3_DEGRADE_V2*/`）：在元数据解析处把 `promptVersion` 降级成 `latest`
  通用 harness、`useDsv3Harness` 置 false，官方守卫原样保留。这正是旧版直连流下 grok 能跑的那条路。
- **能不能跑通取决于服务端是否接受通用 prompt**：grok-4.6 在直连流时代已验证可用；Composer / Auto
  属于试跑，若服务端拒绝会直接报服务端错误。日常仍建议 claude 系列。

## 网页 Usage：会话流 vs 直连流

网页上的 Type / token 是**服务端记账**，不是本地 Context 或 `maxTokens` 补丁能改的。

| 现象                       | 原因                                                               |
| -------------------------- | ------------------------------------------------------------------ |
| **Included + 几十万** 小块 | 直连流自建 `Joe` session，绕开官方 `runInference`，按普通 IDE 记账 |
| **free + 1000 万+**        | 会话流只打标记，走原生会话计费链，记到 sand/bot 额度               |

`1.5.4` 起默认 `--transport session`（与 3.18.25 上 1.7.3 同一修法）。旧版直连若网页 Usage 异常，重跑一次 `install` 即可切到会话流。`--transport direct` 只作兼容回退。

## 免责声明

本工具仅供学习研究，请遵守当地法律法规与 Cursor 服务条款，使用风险自负。

---

## ⭐ 关于 Riot

本工具由 [Riot](https://github.com/caiwuu/Riot) 全程逆向、开发与维护 —— 从定位 Cursor 的 sand 流量封堵，到打通子 agent、工具执行、五模式放行、1M 上下文，每一层补丁都是实打实啃出来的。

如果你觉得这个工具帮到了你，欢迎去 [github.com/caiwuu/Riot](https://github.com/caiwuu/Riot) 点个 Star，支持 Riot 继续维护下去。
