# Cursor Sand Toolkit

> ## ⚡ 由 [Riot](https://github.com/caiwuu/Riot) 打造。
>
> 本项目由 **Riot —— 跑在你机器上的全能智能体** 逆向与维护。
> Riot 能写代码、调研、排查、自动化，把手头的活真正做完，而不是只给建议。
> 觉得这工具好用？**去给 [Riot](https://github.com/caiwuu/Riot) 点个 Star** ⭐

Cursor 客户端模式管理器 —— 伪装 sand 计费到 bot，并绕过后端封堵。

## 能力一览（`install` 一次全生效）

| 能力 | 说明 |
|---|---|
| sand 伪装 | `client-type` → sand，计费到 bot 额度 |
| 绕过封堵 | managed-local 本地推理，绕过后端 sand 流量拒绝 |
| 工具执行 | move-exec 强制 ON，恢复 shell/read/glob 工具 |
| 子 agent（Task） | 本地子 agent，含后台多任务 |
| 五模式放行 | Agent / Ask / Plan / Debug / Multitask 全走本地 |
| 1M 上下文 | maxTokens 覆盖，恢复上下文窗口与压缩 |

## 前提

- Cursor 版本 **3.18.x**（工具会检测，版本不符拒绝安装）
- 账号需已开通 **Sand 资格**（bot 额度）
- 日常建议用 claude 系列模型（grok 偶有额度/行为不稳）

## 下载

去 [Releases](https://github.com/caiwuu/sand/releases) 或 Actions 产物区下载对应平台二进制。

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
./cursor-sand-toolkit install               # 安装/查看状态
./cursor-sand-toolkit uninstall             # 卸载还原
./cursor-sand-toolkit set-path <Cursor路径>  # 指定安装路径（auto 自动检测）
./cursor-sand-toolkit move-exec-check       # 单独检查工具执行补丁
./cursor-sand-toolkit move-exec-apply       # 单独应用
./cursor-sand-toolkit move-exec-restore     # 单独还原
```

## 免责声明

本工具仅供学习研究，请遵守当地法律法规与 Cursor 服务条款，使用风险自负。

---

## ⭐ 关于 Riot

本工具由 [Riot](https://github.com/caiwuu/Riot) 全程逆向、开发与维护 —— 从定位 Cursor 的 sand 流量封堵，到打通子 agent、工具执行、五模式放行、1M 上下文，每一层补丁都是实打实啃出来的。

如果你觉得这个工具帮到了你，欢迎去 [github.com/caiwuu/Riot](https://github.com/caiwuu/Riot) 点个 Star，支持 Riot 继续维护下去。
