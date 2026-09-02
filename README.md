# Cursor Sand Toolkit

> ## ⚡ 由 [Riot](https://github.com/caiwuu/Riot) 打造。
>
> 本项目由 **Riot —— 跑在你机器上的全能智能体** 逆向与维护。
> Riot 能写代码、调研、排查、自动化，把手头的活真正做完，而不是只给建议。
> 觉得这工具好用？**去给 [Riot](https://github.com/caiwuu/Riot) 点个 Star** ⭐

Cursor 客户端模式管理器 —— 伪装 sand 计费到 bot，并绕过后端封堵。

## 能力一览（`install` 一次全生效）

| 能力              | 说明                                                             |
| ----------------- | ---------------------------------------------------------------- |
| sand 伪装         | `client-type` → sand，计费到 bot 额度                            |
| 会话流（默认）    | 复用官方推理链路，网页 Usage 记到 bot / free                     |
| 绕过封堵          | 本地推理，绕过后端 sand 流量拒绝                                 |
| 工具执行          | 恢复 shell / read / glob 等工具                                  |
| 子 agent（Task）  | 本地子 agent，含后台多任务；可选模型跟工作台选择器走               |
| 五模式放行        | Agent / Ask / Plan / Debug / Multitask 全走本地，含 Plan 的 Build |
| 1M 上下文         | 恢复上下文窗口与自动压缩                                         |
| 首字(TTFT)优化    | 每轮固定开销从 ~12s 压到 ~3s                                     |
| Rules/Skills 恢复 | Context Usage 里重新出现 Rules / Skills                          |
| User Rules 注入   | Settings → Rules 里的 User / Team rules 也进 prompt               |
| MCP 恢复          | agent 重新看得到已连接的 MCP server                              |
| Plan 交互修复     | 同一 turn 先提问再建计划不再报错                                 |
| DSV3 模型降级     | Composer / Auto / grok-4.6 可试跑，不再干等 20s 报错             |
| 机器码伪装        | 不再上传真实硬件 UUID / MAC / devDeviceId；假身份持久化，uninstall 也不会还原 |

## 前提

- Cursor 版本 **3.18.9**，且必须是 [Releases](https://github.com/caiwuu/cursor-sand-toolkit/releases) 提供的那份安装包，原因见下
- 账号需已开通 **Sand 资格**（bot 额度）
- 日常建议用 claude 系列模型（grok 偶有额度/行为不稳）

## ⚠️ 必须用本仓库提供的 Cursor 安装包

Cursor 走 CDN 分发，**同一个版本号下可能存在多份构建产物**。它们功能一致，但压缩混淆后的
函数名、变量名不一样。本工具的每一处补丁都是按这些混淆后的名字精确匹配替换的，名字对不上时：

- 好一点的情况是全都匹配不到，`install` 直接报错中止，不会改坏；
- 差一点的情况是只匹配上一部分，装出来半残——比如工具能用但 Rules / MCP 不见了。

所以请下载**本仓库上传的 3.18.9 安装包**，不要用官网或别处下载的 3.18.9。
装完记得**关掉 Cursor 自动更新**，否则一次后台更新就会把补丁连同整个 bundle 覆盖掉。

## 下载

- **Cursor 3.18.9 安装包**：[Releases](https://github.com/caiwuu/cursor-sand-toolkit/releases)（务必用这份）
- **本工具二进制**：同样在 [Releases](https://github.com/caiwuu/cursor-sand-toolkit/releases)，按平台选

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

## 命令一览

```bash
./cursor-sand-toolkit install               # 安装（默认会话流）
./cursor-sand-toolkit install --transport direct   # 直连流，仅在会话流有问题时回退
./cursor-sand-toolkit uninstall             # 卸载还原
./cursor-sand-toolkit set-path <Cursor路径>  # 指定 Cursor 路径（auto 恢复自动检测）

./cursor-sand-toolkit move-exec-check       # 工具执行补丁：检查 / 应用 / 还原
./cursor-sand-toolkit move-exec-apply
./cursor-sand-toolkit move-exec-restore

./cursor-sand-toolkit ttft-check            # 首字延迟优化：检查 / 应用 / 还原
./cursor-sand-toolkit ttft-apply
./cursor-sand-toolkit ttft-restore
./cursor-sand-toolkit ttft-sync             # 同步 product.json 校验和（修复「安装已损坏」）

./cursor-sand-toolkit rules-skills-check    # 检查 Rules/Skills 恢复补丁

./cursor-sand-toolkit machine-id-check      # 检查机器码伪装
```

不带参数运行会打印当前状态：Cursor 版本与路径、各补丁是否生效。排查问题先看这个。

## 常见问题

**装完某项能力没生效？**
不带参数跑一次，看状态里对应那行是不是「未启用」。是的话重跑 `install`。

**Cursor 提示「安装已损坏」？**
跑 `ttft-sync` 同步校验和。

**Cursor 更新后全部失效？**
自动更新会覆盖整个 bundle。重新装回 3.18.9 那份安装包，再跑一次 `install`，然后关掉自动更新。

**`install` 报「未完整匹配 Sand Stream 规则」？**
说明你的 Cursor 不是本仓库提供的那份构建，见上面的警告。此时 Cursor 未被修改，可放心换包重来。

**网页 Usage 显示成 Included 和几十万的小块？**
是旧版直连流的记账方式。重跑一次 `install` 切回默认的会话流即可，已产生的记录不会改写。

**卸载后还会不会上传真实机器码？**
不会。`uninstall` 只还原 Sand 功能补丁，机器码伪装会留下。同一台机器重装也继续用同一套假身份。

## 免责声明

本工具仅供学习研究，请遵守当地法律法规与 Cursor 服务条款，使用风险自负。

---

## ⭐ 关于 Riot

本工具由 [Riot](https://github.com/caiwuu/Riot) 全程逆向、开发与维护 —— 从定位 Cursor 的 sand 流量封堵，到打通子 agent、工具执行、五模式放行、1M 上下文，每一层补丁都是实打实啃出来的。

如果你觉得这个工具帮到了你，欢迎去 [github.com/caiwuu/Riot](https://github.com/caiwuu/Riot) 点个 Star，支持 Riot 继续维护下去。
