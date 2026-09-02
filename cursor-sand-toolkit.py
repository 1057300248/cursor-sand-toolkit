"""Sand Stream Toolkit。

交互式运行：
    python sand_stream_installer.py

命令行运行：
    python sand_stream_installer.py install
    python sand_stream_installer.py install --transport direct
    python sand_stream_installer.py uninstall
    python sand_stream_installer.py set-path <Cursor路径|auto>
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union


TOOL_NAME = "Sand Stream Toolkit"
TOOL_VERSION = "1.5.5"
SUPPORTED_CURSOR_VERSION = "3.18.9"
CONFIG_VERSION = 1
STREAM_TRANSPORT_SESSION = "session"
STREAM_TRANSPORT_DIRECT = "direct"
STREAM_TRANSPORTS = (STREAM_TRANSPORT_SESSION, STREAM_TRANSPORT_DIRECT)

SAND_CLIENT_MARKER = "/*SAND_CLIENT_MODE_V1*/"
SAND_CLIENT_EXISTING_MARKER = "/*SAND_CLIENT_EXISTING_V1*/"
SAND_ELIGIBILITY_MARKER = "/*SAND_ELIGIBILITY_MODE_V1*/"
SAND_MANAGED_LOCAL_ROUTE_MARKER = "/*SAND_MANAGED_LOCAL_ROUTE_V1*/"
SAND_SESSION_STREAM_MARKER = "/*SAND_SESSION_INFERENCE_STREAM_V1*/"
SAND_DIRECT_STREAM_MARKER = "/*SAND_DIRECT_INFERENCE_STREAM_V1*/"
# —— DSV3（Composer/Auto/grok-4.6）模型 ——
# 3.18.9 的本地运行时没有 DSV3 harness 实现（dsv31018ToolsGenerator 只出现在报错串里）。
# V1（fork 移植）只是屏蔽 useDsv3Harness 守卫，让请求继续往下走到 doe() 里抛
# "Tools for dsv3-1018 are handled in dsv31018ToolsGenerator"，还要重试 3 次。
# V2 改在元数据解析处降级：useDsv3Harness 时把 promptVersion 换成 "latest"（通用 harness，
# 即旧版 direct 流下 grok 能跑的那条路），并把 useDsv3Harness 置 false，官方守卫原样保留。
SAND_DSV3_LOCAL_LOOP_MARKER_V1 = "/*SAND_DSV3_LOCAL_LOOP_V1*/"
SAND_DSV3_DEGRADE_MARKER = "/*SAND_DSV3_DEGRADE_V2*/"
SAND_AGENT_HOST_ENABLEMENT_MARKER = "/*SAND_AGENT_HOST_ENABLEMENT_V1*/"
SAND_LOCAL_RUNTIME_LOAD_MARKER = "/*SAND_LOCAL_RUNTIME_LOAD_V1*/"
SAND_AGENT_HOST_IDENTITY_MARKER = "/*SAND_AGENT_HOST_IDENTITY_V1*/"
SAND_MOVE_EXEC_MARKER = "/*SAND_MOVE_EXEC_V1*/"
MOVE_EXEC_ORIGINAL = (
    "p=await Promise.resolve(r.cursor.checkFeatureGate(Us)).catch(()=>!1)"
)
MOVE_EXEC_PATCHED = "p=!0" + SAND_MOVE_EXEC_MARKER
# —— 子 agent（Task 工具）激活 ——
SAND_TASK_TOOL_MARKER = "/*SAND_TASK_TOOL_V1*/"
TASK_TOOL_ORIGINAL = "taskToolProps:void 0"
TASK_TOOL_PATCHED = (
    "taskToolProps:{parentRequestedModelName:i,parentModelParameters:void 0,"
    "parentMaxMode:l,isModelBlocked:()=>!1,isModelValid:()=>!0,"
    "requiresMaxMode:()=>!1,forceModelId:void 0,compareModelCosts:()=>0,"
    'subagentModelForcePolicy:"none",requireServerSideSubagent:!1,'
    "subagentModels:{modelsBySlug:new Map},subagentModelOverrides:{},"
    "normalizeCustomSubagents:e=>e,enableGrindSwarmSubagent:!1,"
    "enableBrowserSubagent:!1,"
    "getTaskToolConfig:()=>async()=>({})" + SAND_TASK_TOOL_MARKER + "}"
)
SAND_CLIENT_SIDE_SUBAGENT_MARKER = "/*SAND_CLIENT_SIDE_SUBAGENT_V1*/"
CLIENT_SIDE_SUBAGENT_ORIGINAL = (
    "const Cre={enableEmptyResponseRetry:!0,enableGrepBroadGlobGuard:!0,"
    "enableReadToolNegativeOffset:!0,enableSandboxSharedBuildCache:!0,"
    "nalLoopDetection:!0}"
)
CLIENT_SIDE_SUBAGENT_PATCHED = (
    "const Cre={enableEmptyResponseRetry:!0,enableGrepBroadGlobGuard:!0,"
    "enableReadToolNegativeOffset:!0,enableSandboxSharedBuildCache:!0,"
    "nalLoopDetection:!0,useClientSideSubagent:!0"
    + SAND_CLIENT_SIDE_SUBAGENT_MARKER
    + "}"
)
SAND_SUBAGENT_TURN_MARKER = "/*SAND_SUBAGENT_TURN_V1*/"
SAND_SUBAGENT_FOLLOWUP_MARKER = "/*SAND_SUBAGENT_FOLLOWUP_V1*/"
SAND_PLAN_BUILD_MARKER = "/*SAND_PLAN_BUILD_V1*/"
SUBAGENT_TURN_N_OLD = (
    "hasUnsupportedRunOptions:void 0!==e.runOptions.customSystemPrompt||"
    "void 0!==e.runOptions.harness||"
    "!0===e.runOptions.excludeWorkspaceContext||"
    "void 0!==e.runOptions.subagentTypeName||"
    "void 0!==e.runOptions.parentAgentToolCallId||"
    "!0===e.runOptions.directMetaParentChildSubagent"
)
SUBAGENT_TURN_N_NEW = (
    SUBAGENT_TURN_N_OLD + ",isSubagentTurn:void 0!==e.runOptions.subagentTypeName||"
    "void 0!==e.runOptions.parentAgentToolCallId"
)
SUBAGENT_ROUTE_ORIGINAL = (
    'return"userMessageAction"!==e.actionCase?"action-not-supported":'
)
# V1：只放行 followup + 子 agent turn。Plan Build 走 executePlanAction，
# 仍被判 action-not-supported → runtime connect → 后端拒 sand → Connection failed。
SUBAGENT_ROUTE_PATCHED_V1 = (
    'return"backgroundTaskCompletionAction"===e.actionCase?void 0:'
    + SAND_SUBAGENT_FOLLOWUP_MARKER
    + "e.isSubagentTurn?void 0:"
    + SAND_SUBAGENT_TURN_MARKER
    + '"userMessageAction"!==e.actionCase?"action-not-supported":'
)
SUBAGENT_ROUTE_PATCHED = (
    'return"backgroundTaskCompletionAction"===e.actionCase||'
    '"executePlanAction"===e.actionCase||'
    '"resumeAction"===e.actionCase?void 0:'
    + SAND_PLAN_BUILD_MARKER
    + SAND_SUBAGENT_FOLLOWUP_MARKER
    + "e.isSubagentTurn?void 0:"
    + SAND_SUBAGENT_TURN_MARKER
    + '"userMessageAction"!==e.actionCase?"action-not-supported":'
)
# —— MCP FileSystem 提示块恢复 ——
# 675.js 的 O$() 只有在 mcpMetaToolOptions.enabled，或
# featureFlags.enableMCPFileSystem 为真时才把 <mcp_file_system> 写进 system prompt。
# 这个 flag 由服务端随会话下发，sand/managed-local 拿不到，于是 agent 不知道有哪些
# MCP server（Context Usage 里 MCP 整类为 0），尽管 exec 已把描述写进 <projectDir>/mcps。
SAND_MCP_FILESYSTEM_MARKER = "/*SAND_MCP_FILESYSTEM_V1*/"
# —— 机器码伪装 ——
# 只改 storage.json 不够：abuseService._getTrueMachineId 会再跑一遍 ioreg / MachineGuid。
# 必须改 main.js 的 K6（硬件 UUID）、B9e（MAC）、z6（devDeviceId）。
# kBe 每次启动会用 z6() 覆盖 storage 里的 telemetry.devDeviceId。
# uninstall 不还原这三处，避免真实机器码再次上传。
SAND_MACHINE_ID_MARKER = "/*SAND_MACHINE_ID_V1*/"
SAND_MACHINE_MAC_MARKER = "/*SAND_MACHINE_MAC_V1*/"
SAND_MACHINE_DEV_MARKER = "/*SAND_MACHINE_DEV_V1*/"
MACHINE_ID_K6_ORIGINAL = (
    "async function K6(e){let t=H9e($9e(J6[sR],{timeout:5e3}).toString()),n;"
    'try{n=(await import("crypto")).createHash("sha256").update(t,"utf8").digest("hex")}'
    "catch{n=dt()}return e?t:n}"
)
MACHINE_MAC_B9E_ORIGINAL = (
    "function B9e(){const e=F9e();for(const t in e){const n=e[t];if(n){"
    "for(const{mac:r}of n)if(W9e(r))return r}}"
    'throw new Error("Unable to retrieve mac address (unexpected format)")}'
)
MACHINE_ID_K6_PATCHED_RE = re.compile(
    r"async function K6\(e\)\{const t=\"[0-9a-fA-F-]{36}\""
    + re.escape(SAND_MACHINE_ID_MARKER)
    + r";"
    r'let n;try\{n=\(await import\("crypto"\)\)\.createHash\("sha256"\)'
    r'\.update\(t,"utf8"\)\.digest\("hex"\)\}catch\{n=dt\(\)\}return e\?t:n\}'
)
MACHINE_MAC_B9E_PATCHED_RE = re.compile(
    r"function B9e\(\)\{return\"[0-9a-f:]{17}\""
    + re.escape(SAND_MACHINE_MAC_MARKER)
    + r"\}"
)
MACHINE_DEV_Z6_ORIGINAL = (
    'async function z6(e){try{return await(await import("@vscode/deviceid")).getDeviceId()}'
    "catch(t){return e(t),dt()}}"
)
MACHINE_DEV_Z6_PATCHED_RE = re.compile(
    r"async function z6\(e\)\{return\"[0-9a-fA-F-]{36}\""
    + re.escape(SAND_MACHINE_DEV_MARKER)
    + r"\}"
)
MCP_FILESYSTEM_ORIGINAL = (
    "const t=e.requestContext?.mcpFileSystemOptions,"
    "n=!0===e.featureFlags?.enableMCPFileSystem,"
    'o=t?.workspaceProjectDir??""'
)
MCP_FILESYSTEM_PATCHED = (
    "const t=e.requestContext?.mcpFileSystemOptions,"
    "n=!0" + SAND_MCP_FILESYSTEM_MARKER + ","
    'o=t?.workspaceProjectDir??""'
)
SAND_MAX_TOKENS_MARKER = "/*SAND_MAX_TOKENS_V1*/"
SAND_MODE_RELAX_MARKER = "/*SAND_MODE_RELAX_V1*/"
MODE_RELAX_ORIGINAL = 'e.requestedMode!==oe.xyI.AGENT?"mode-not-supported":'
MODE_RELAX_PATCHED = "!1?" + SAND_MODE_RELAX_MARKER + '"mode-not-supported":'
MAX_TOKENS_ORIGINAL = (
    "t.resolveExtendedUsage({inputTokens:n.inputTokens,"
    "outputTokens:n.outputTokens,cacheReadTokens:n.cacheReadTokens,"
    "cacheWriteTokens:n.cacheWriteTokens,maxTokens:n.maxTokens})"
)
MAX_TOKENS_PATCHED = (
    "t.resolveExtendedUsage({inputTokens:n.inputTokens,"
    "outputTokens:n.outputTokens,cacheReadTokens:n.cacheReadTokens,"
    "cacheWriteTokens:n.cacheWriteTokens,maxTokens:(()=>{"
    'const c=this.requestedModel?.parameters?.find(p=>p.id==="context")?.value;'
    "if(void 0===c)return n.maxTokens;"
    "const s=String(c).trim().toLowerCase();const num=parseFloat(s);"
    "if(!Number.isFinite(num)||num<=0)return n.maxTokens;"
    'const mult=s.endsWith("k")?1e3:s.endsWith("m")?1e6:s.endsWith("b")?1e9:1;'
    "return num*mult})()})" + SAND_MAX_TOKENS_MARKER
)
# —— 首字(TTFT)延迟优化：buildFromPushedData 等待 pushed rules 的内置超时 10s → 1s ——
# 不同版本 minify 后的超时常量名不同：3.18.25 用 yCd，3.18.9 用 Ykd；值均为 1e4
SAND_TTFT_MARKER = "/*SAND_TTFT_V1*/"
TTFT_TIMEOUT_VARS = ("yCd", "Ykd")
TTFT_ORIGINALS = tuple(f"{var}=1e4" for var in TTFT_TIMEOUT_VARS)
TTFT_RESTORE_RE = re.compile(
    rf"([A-Za-z_$][A-Za-z0-9_$]*)=1e3{re.escape(SAND_TTFT_MARKER)}"
)
# —— Rules/Skills 恢复 ——
# cursor-agent-exec 的 aa() 在 cursorAgentHostEnabled 时只 registerAgentHostRuntime，
# 不调用 na()（activateCursorAgentRuntime）。na() 才会 updateCursorRules/updateAgentSkills。
# Sand 打开 agent-host 后这条链路被跳过，Context Usage 里 Rules/Skills 整类消失。
# V4：直接改 aa()，host 启用时仍跑 na({registerAgentExecProvider:!1})，并置 ia=!0
# 以便扩展停用走 ra()。不再从 host 侧 createLiveExecRuntime 抢跑（V1–V3）。
SAND_RULES_SKILLS_MARKER = "/*SAND_RULES_SKILLS_V4*/"
SAND_RULES_SKILLS_MARKER_V3 = "/*SAND_RULES_SKILLS_V3*/"
SAND_RULES_SKILLS_MARKER_V2 = "/*SAND_RULES_SKILLS_V2*/"
SAND_RULES_SKILLS_MARKER_V1 = "/*SAND_RULES_SKILLS_V1*/"
RULES_SKILLS_EXEC_RUNTIME_MODULE = "71385"
RULES_SKILLS_EXEC_ORIGINAL = (
    "async function aa(e){if(j.cursor.cursorAgentHostEnabled){"
    "const r=(t=oa,n=e.extensionPath,{...t,extensionPath:n});"
    "return void e.subscriptions.push(j.cursor.registerAgentHostRuntime(r))}"
    "var t,n;j.cursor.cursorAgentHostEnabled||(await na(e),ia=!0)}"
)
RULES_SKILLS_EXEC_PATCHED = (
    "async function aa(e){if(j.cursor.cursorAgentHostEnabled){"
    "const r=(t=oa,n=e.extensionPath,{...t,extensionPath:n});"
    "e.subscriptions.push(j.cursor.registerAgentHostRuntime(r));"
    + SAND_RULES_SKILLS_MARKER
    + "await na(e,{registerAgentExecProvider:!1,"
    "runtimeExtensionPath:e.extensionPath}),ia=!0;return}"
    "var t,n;j.cursor.cursorAgentHostEnabled||(await na(e),ia=!0)}"
)
# 以下为 host 侧旧注入，仅用于剥离，不再新打。
RULES_SKILLS_HOST_ORIGINAL = "i.subscriptions.push({dispose:()=>T.dispose()});"
RULES_SKILLS_PATCHED_V3 = (
    RULES_SKILLS_HOST_ORIGINAL
    + SAND_RULES_SKILLS_MARKER_V3
    + "try{const{createLiveExecRuntime:_sr}=await Promise.resolve().then("
    + f"s.bind(s,{RULES_SKILLS_EXEC_RUNTIME_MODULE}));"
    + "zs=await _sr({acquireTimeoutMs:2e3});"
    + "await zs.activate(i,{registerAgentExecProvider:!1,"
    + "runtimeExtensionPath:zs.extensionPath})"
    + '}catch(_se){D.error("[SAND] rules/skills activation failed",_se)}'
)
RULES_SKILLS_PATCHED_V2 = (
    RULES_SKILLS_HOST_ORIGINAL
    + SAND_RULES_SKILLS_MARKER_V2
    + "try{const{createLiveExecRuntime:_sr}=await Promise.resolve().then("
    + f"s.bind(s,{RULES_SKILLS_EXEC_RUNTIME_MODULE}));"
    + "const _sz=await _sr();"
    + "await _sz.activate(i,{registerAgentExecProvider:!1,"
    + "runtimeExtensionPath:_sz.extensionPath})"
    + '}catch(_se){D.error("[SAND] rules/skills activation failed",_se)}'
)
RULES_SKILLS_PATCHED_V1 = (
    RULES_SKILLS_HOST_ORIGINAL
    + SAND_RULES_SKILLS_MARKER_V1
    + "try{const{createLiveExecRuntime:_sr}=await Promise.resolve().then("
    + f"s.bind(s,{RULES_SKILLS_EXEC_RUNTIME_MODULE}));"
    + "const _sz=await _sr();"
    + "await _sz.activate(i,{registerAgentExecProvider:!1,"
    + "runtimeExtensionPath:_sz.extensionPath,gitExecutor:w,mcpProvider:T})"
    + '}catch(_se){D.error("[SAND] rules/skills activation failed",_se)}'
)
_RULES_SKILLS_LEGACY_PAYLOADS: Tuple[Tuple[str, str], ...] = (
    (SAND_RULES_SKILLS_MARKER_V3, RULES_SKILLS_PATCHED_V3),
    (SAND_RULES_SKILLS_MARKER_V2, RULES_SKILLS_PATCHED_V2),
    (SAND_RULES_SKILLS_MARKER_V1, RULES_SKILLS_PATCHED_V1),
)
JS_IDENTIFIER_PATTERN = r"[A-Za-z_$][A-Za-z0-9_$]*"
# —— User Rules（Settings → Rules 里的非文件规则）注入 ——
# 云端链路上 User/Team rules 由服务端拼进 prompt；managed-local 本地拼 prompt 时，
# workbench 的 injectLocalModeNonFileRules 只在 localMode 才把 knowledgeBase 里的
# User Rules 并进 requestContext.rules，于是 Context Usage 里 Rules 恒为 0。
# 打掉这个守卫，让 buildFromPushedData 始终注入（sand 全走本地，不会与服务端重复）。
SAND_USER_RULES_MARKER = "/*SAND_USER_RULES_V1*/"
USER_RULES_ORIGINAL_RE = re.compile(
    r"injectLocalModeNonFileRules\(e\)\{if\(!(?P<flags>"
    + JS_IDENTIFIER_PATTERN
    + r")\.localMode\)return;"
)
USER_RULES_PATCHED_RE = re.compile(
    r"injectLocalModeNonFileRules\(e\)\{if\(!1&&!(?P<flags>"
    + JS_IDENTIFIER_PATTERN
    + r")\.localMode\)return;"
    + re.escape(SAND_USER_RULES_MARKER)
)
# —— 同一 turn 多次交互（AskQuestion → CreatePlan）串号修复 ——
# agent-host 的 interaction registry 用 `${turnId}:${query.id}` 做 key，而本地 loop
# 构造 InteractionQuery 时从不填 id（uint32，恒为 0）。同一 turn 里第二个交互会直接
# 命中第一个已缓存的应答：Plan 模式先问再建计划时 create_plan 拿到
# askQuestionInteractionResponse，报 "Unexpected response for create plan query"。
# 官方在 queryFromChild / querySurfacedForSubagent 里都带了 seq，唯独主会话 query 漏了。
SAND_INTERACTION_SEQ_MARKER = "/*SAND_INTERACTION_SEQ_V1*/"
INTERACTION_SEQ_ORIGINAL_RE = re.compile(
    r"query\(e,t\)\{return (?P<awaiter>"
    + JS_IDENTIFIER_PATTERN
    + r")\(this,void 0,void 0,function\*\(\)\{const n=this\.activeTurnId;"
    r"if\(void 0===n\)throw new Error\(`Agent host interaction query has no active turn: "
    r"\$\{this\.sessionId\}`\);return this\.registry\.query\(e,n,t\)\}\)\}"
)
INTERACTION_SEQ_PATCHED_RE = re.compile(
    r"query\(e,t\)\{return (?P<awaiter>"
    + JS_IDENTIFIER_PATTERN
    + r")\(this,void 0,void 0,function\*\(\)\{const n=this\.activeTurnId;"
    r"if\(void 0===n\)throw new Error\(`Agent host interaction query has no active turn: "
    r"\$\{this\.sessionId\}`\);"
    + re.escape(SAND_INTERACTION_SEQ_MARKER)
    + r"const s=this\.sandInteractionSeq=\(this\.sandInteractionSeq\?\?0\)\+1;"
    r"return this\.registry\.query\(e,n,t,\{interactionId:`\$\{n\}:\$\{t\.id\}:\$\{s\}`\}\)\}\)\}"
)


def _interaction_seq_patched(awaiter: str) -> str:
    return (
        "query(e,t){return "
        + awaiter
        + "(this,void 0,void 0,function*(){const n=this.activeTurnId;"
        "if(void 0===n)throw new Error(`Agent host interaction query has no active turn: "
        "${this.sessionId}`);"
        + SAND_INTERACTION_SEQ_MARKER
        + "const s=this.sandInteractionSeq=(this.sandInteractionSeq??0)+1;"
        "return this.registry.query(e,n,t,{interactionId:`${n}:${t.id}:${s}`})})}"
    )


def _interaction_seq_original(awaiter: str) -> str:
    return (
        "query(e,t){return "
        + awaiter
        + "(this,void 0,void 0,function*(){const n=this.activeTurnId;"
        "if(void 0===n)throw new Error(`Agent host interaction query has no active turn: "
        "${this.sessionId}`);return this.registry.query(e,n,t)})}"
    )


LEGACY_SAND_CLIENT_MARKER = "/*K" + "C_SAND_CLIENT_V1*/"
LEGACY_SAND_ELIGIBILITY_MARKER = "/*K" + "C_SAND_ELIGIBILITY_V1*/"
CLIENT_MARKER_PATTERN = re.escape(SAND_CLIENT_MARKER)
CLIENT_EXISTING_MARKER_PATTERN = re.escape(SAND_CLIENT_EXISTING_MARKER)
ELIGIBILITY_MARKER_PATTERN = re.escape(SAND_ELIGIBILITY_MARKER)
LEGACY_CLIENT_MARKER_PATTERN = re.escape(LEGACY_SAND_CLIENT_MARKER)
LEGACY_ELIGIBILITY_MARKER_PATTERN = re.escape(LEGACY_SAND_ELIGIBILITY_MARKER)
CLIENT_MARKER_GUARD_PATTERN = r"/\*[A-Z0-9_]*SAND_CLIENT(?:_(?:MODE|EXISTING))?_V1\*/"
ELIGIBILITY_MARKER_GUARD_PATTERN = r"/\*[A-Z0-9_]*SAND_ELIGIBILITY(?:_MODE)?_V1\*/"
SAND_ONBOARDING_URL = "https://cursor.com/bot/onboarding?product=grok-bot"

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[36m"

_COLOR_ENABLED = True


TARGET_SPECS: Tuple[Tuple[str, Optional[str]], ...] = (
    ("out/main.js", None),
    ("out/vs/workbench/api/worker/extensionHostWorkerMain.js", None),
    ("out/vs/workbench/api/node/extensionHostProcess.js", None),
    ("out/vs/workbench/workbench.glass.main.js", None),
    ("out/vs/workbench/workbench.desktop.main.js", None),
    ("extensions/cursor-always-local/dist/main.js", "cursor-always-local"),
    (
        "extensions/cursor-local-agent-runtime/dist/main.js",
        "cursor-local-agent-runtime",
    ),
    ("extensions/cursor-agent-host/dist/main.js", "cursor-agent-host"),
    ("extensions/cursor-agent-exec/dist/main.js", "cursor-agent-exec"),
    ("extensions/cursor-agent-host/dist/657.js", None),
    ("extensions/cursor-agent-host/dist/675.js", None),
)

EXT_HOST_REL = "out/vs/workbench/api/node/extensionHostProcess.js"

ELIGIBILITY_PREFIXES: Tuple[str, ...] = (
    "function r4g(e){const{adminSettingsService:t",
    "function Vj_(t){const{adminSettingsService:e",
    "function inf(e){const{adminSettingsService:t",
    "function HSy(t){const{adminSettingsService:e",
    "function Q_f(e){const{adminSettingsService:t",
    "function BpS(t){const{adminSettingsService:e",
)


class SandToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class CursorLayout:
    install_root: Path
    app_root: Path
    product_json: Path
    executable: Path
    target_paths: Tuple[Path, ...]
    ext_host_path: Optional[Path]
    version: str


@dataclass(frozen=True)
class PlannedFile:
    original: bytes
    next_bytes: bytes
    mode: int


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_MAC_SPOOF_RE = re.compile(
    r"^02:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}$",
    re.IGNORECASE,
)
_SQM_RE = re.compile(
    r"^\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}$"
)


@dataclass(frozen=True)
class SpoofedIdentity:
    raw_machine_uuid: str
    machine_id: str
    mac_address: str
    mac_machine_id: str
    dev_device_id: str
    sqm_id: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "rawMachineUuid": self.raw_machine_uuid,
            "machineId": self.machine_id,
            "macAddress": self.mac_address,
            "macMachineId": self.mac_machine_id,
            "devDeviceId": self.dev_device_id,
            "sqmId": self.sqm_id,
        }


@dataclass
class PatchStats:
    is_glass: int = 0
    object_header: int = 0
    set_header: int = 0
    eligibility: int = 0
    adopted_sand: int = 0
    migrated_client: int = 0
    migrated_eligibility: int = 0
    managed_local_route: int = 0
    local_runtime_load: int = 0
    session_stream: int = 0
    direct_stream: int = 0
    dsv3_local_loop: int = 0
    agent_host_enablement: int = 0
    agent_host_identity: int = 0
    move_exec: int = 0
    task_tool: int = 0
    client_side_subagent: int = 0
    subagent_turn: int = 0
    ttft: int = 0
    rules_skills: int = 0
    user_rules: int = 0
    mcp_filesystem: int = 0
    interaction_seq: int = 0
    machine_id: int = 0
    machine_mac: int = 0
    machine_dev: int = 0

    @property
    def total(self) -> int:
        return (
            self.is_glass
            + self.object_header
            + self.set_header
            + self.eligibility
            + self.migrated_client
            + self.migrated_eligibility
            + self.managed_local_route
            + self.local_runtime_load
            + self.session_stream
            + self.direct_stream
            + self.dsv3_local_loop
            + self.agent_host_enablement
            + self.agent_host_identity
            + self.move_exec
            + self.task_tool
            + self.client_side_subagent
            + self.subagent_turn
            + self.ttft
            + self.rules_skills
            + self.user_rules
            + self.mcp_filesystem
            + self.interaction_seq
            + self.machine_id
            + self.machine_mac
            + self.machine_dev
        )


@dataclass
class RemoveStats:
    client_type: int = 0
    eligibility: int = 0
    managed_local_route: int = 0
    local_runtime_load: int = 0
    session_stream: int = 0
    direct_stream: int = 0
    dsv3_local_loop: int = 0
    agent_host_enablement: int = 0
    agent_host_identity: int = 0
    move_exec: int = 0
    task_tool: int = 0
    client_side_subagent: int = 0
    subagent_turn: int = 0
    ttft: int = 0
    rules_skills: int = 0
    user_rules: int = 0
    mcp_filesystem: int = 0
    interaction_seq: int = 0

    @property
    def total(self) -> int:
        return (
            self.client_type
            + self.eligibility
            + self.managed_local_route
            + self.local_runtime_load
            + self.session_stream
            + self.direct_stream
            + self.dsv3_local_loop
            + self.agent_host_enablement
            + self.agent_host_identity
            + self.move_exec
            + self.task_tool
            + self.client_side_subagent
            + self.subagent_turn
            + self.ttft
            + self.rules_skills
            + self.user_rules
            + self.mcp_filesystem
            + self.interaction_seq
        )


@dataclass(frozen=True)
class PatchStatus:
    client_markers: int
    eligibility_markers: int
    ide_matches: int
    external_sand_matches: int
    external_marker_count: int
    legacy_client_markers: int
    legacy_eligibility_markers: int
    patched_files: Tuple[Path, ...]
    managed_local_route_markers: int
    local_runtime_load_markers: int
    session_stream_markers: int
    direct_stream_markers: int
    dsv3_local_loop_markers: int
    agent_host_enablement_markers: int
    agent_host_identity_markers: int
    move_exec_markers: int
    task_tool_markers: int
    client_side_subagent_markers: int
    subagent_turn_markers: int
    ttft_markers: int
    rules_skills_markers: int
    rules_skills_legacy_markers: int
    dsv3_legacy_markers: int
    user_rules_markers: int
    mcp_filesystem_markers: int
    interaction_seq_markers: int
    machine_id_markers: int
    machine_mac_markers: int
    machine_dev_markers: int

    @property
    def machine_id_spoofed(self) -> bool:
        return (
            self.machine_id_markers == 1
            and self.machine_mac_markers == 1
            and self.machine_dev_markers == 1
        )

    @property
    def installed(self) -> bool:
        return (
            self.client_markers
            + self.eligibility_markers
            + self.legacy_client_markers
            + self.legacy_eligibility_markers
            + self.managed_local_route_markers
            + self.local_runtime_load_markers
            + self.session_stream_markers
            + self.direct_stream_markers
            + self.dsv3_local_loop_markers
            + self.dsv3_legacy_markers
            + self.agent_host_enablement_markers
            + self.agent_host_identity_markers
            > 0
        )

    @property
    def stream_transport(self) -> Optional[str]:
        if self.session_stream_markers == 1 and self.direct_stream_markers == 0:
            return STREAM_TRANSPORT_SESSION
        if self.direct_stream_markers == 1 and self.session_stream_markers == 0:
            return STREAM_TRANSPORT_DIRECT
        return None

    @property
    def stream_mode_installed(self) -> bool:
        return (
            self.managed_local_route_markers > 0
            and self.local_runtime_load_markers > 0
            and self.dsv3_local_loop_markers > 0
            and self.stream_transport is not None
            and self.agent_host_enablement_markers > 0
            and self.agent_host_identity_markers > 0
        )


def _compile_client_rules() -> Tuple[Tuple[str, re.Pattern[str]], ...]:
    marker_guard = rf"(?!{CLIENT_MARKER_GUARD_PATTERN})"
    return (
        (
            "is_glass",
            re.compile(
                rf"(isGlass\s*\?\s*[\"']glass[\"']\s*:\s*)([\"'])(ide|sand)\2{marker_guard}"
            ),
        ),
        (
            "object_header",
            re.compile(
                rf"([\"']x-cursor-client-type[\"']\s*:\s*)([\"'])(ide|sand)\2{marker_guard}"
            ),
        ),
        (
            "set_header",
            re.compile(
                rf"(header\.set\(\s*[\"']x-cursor-client-type[\"']\s*,\s*"
                rf"[A-Za-z_$][A-Za-z0-9_$.]*\s*(?:\?\?|\|\|)\s*)"
                rf"([\"'])(ide|sand)\2{marker_guard}"
            ),
        ),
    )


CLIENT_RULES = _compile_client_rules()

MANAGED_LOCAL_ROUTE_ORIGINAL = (
    "try{return(yield o.checkFeatureGate(ae))?"
    '{runtime:"managed-local",reason:"eligible"}:'
    '{runtime:"connect",reason:"gate-off"}}catch(e)'
)
MANAGED_LOCAL_ROUTE_PATCHED = (
    "try{return"
    + SAND_MANAGED_LOCAL_ROUTE_MARKER
    + '{runtime:"managed-local",reason:"sand-client"}}catch(e)'
)
LOCAL_RUNTIME_LOAD_ORIGINAL = "let t=!1;try{t=await r.cursor.checkFeatureGate(Ds)}"
LOCAL_RUNTIME_LOAD_PATCHED = "let t=!0;" + SAND_LOCAL_RUNTIME_LOAD_MARKER + "try{t=!0}"
AGENT_HOST_IDENTITY_ORIGINAL = 'clientIdentity:{clientType:"ide"}'
AGENT_HOST_IDENTITY_PATCHED = (
    'clientIdentity:{clientType:"sand"' + SAND_AGENT_HOST_IDENTITY_MARKER + "}"
)
# V1 守卫补丁（仅用于剥离还原，不再新打）
DSV3_LOCAL_LOOP_GUARD_RE = re.compile(
    r"if\((?P<metadata>"
    + JS_IDENTIFIER_PATTERN
    + r")\.useDsv3Harness\)throw new (?P<error>"
    + JS_IDENTIFIER_PATTERN
    + r')\("dsv3-harness-not-supported",(?P<model>'
    + JS_IDENTIFIER_PATTERN
    + r")\);"
)
DSV3_LOCAL_LOOP_PATCHED_V1_RE = re.compile(
    r"if\(!1&&(?P<metadata>"
    + JS_IDENTIFIER_PATTERN
    + r")\.useDsv3Harness\)"
    + re.escape(SAND_DSV3_LOCAL_LOOP_MARKER_V1)
    + r"throw new (?P<error>"
    + JS_IDENTIFIER_PATTERN
    + r')\("dsv3-harness-not-supported",(?P<model>'
    + JS_IDENTIFIER_PATTERN
    + r")\);"
)
# V2 元数据降级：function nre(e,t){if(void 0!==e)return{promptModelInfo:ore(e,t),
#   useDsv3Harness:e.useDsv3Harness,agentTokenLimit:...,estimatedCacheTtlMs:...}}
DSV3_METADATA_RESOLVER_RE = re.compile(
    r"function (?P<resolver>"
    + JS_IDENTIFIER_PATTERN
    + r")\(e,t\)\{if\(void 0!==e\)return\{promptModelInfo:(?P<info>"
    + JS_IDENTIFIER_PATTERN
    + r")\(e,t\),useDsv3Harness:e\.useDsv3Harness,agentTokenLimit:e\.agentTokenLimit,"
    r"estimatedCacheTtlMs:e\.estimatedCacheTtlMs\}\}"
)
DSV3_METADATA_DEGRADED_RE = re.compile(
    r"function (?P<resolver>"
    + JS_IDENTIFIER_PATTERN
    + r")\(e,t\)\{if\(void 0!==e\)return\{promptModelInfo:(?P<info>"
    + JS_IDENTIFIER_PATTERN
    + r")\(e\.useDsv3Harness\?"
    + re.escape(SAND_DSV3_DEGRADE_MARKER)
    + r'Object\.assign\(\{\},e,\{promptVersion:"latest"\}\):e,t\),useDsv3Harness:!1,'
    r"agentTokenLimit:e\.agentTokenLimit,estimatedCacheTtlMs:e\.estimatedCacheTtlMs\}\}"
)


def _dsv3_metadata_original(resolver: str, info: str) -> str:
    return (
        f"function {resolver}(e,t){{if(void 0!==e)return{{promptModelInfo:{info}(e,t),"
        "useDsv3Harness:e.useDsv3Harness,agentTokenLimit:e.agentTokenLimit,"
        "estimatedCacheTtlMs:e.estimatedCacheTtlMs}}"
    )


def _dsv3_metadata_degraded(resolver: str, info: str) -> str:
    return (
        f"function {resolver}(e,t){{if(void 0!==e)return{{promptModelInfo:{info}("
        "e.useDsv3Harness?"
        + SAND_DSV3_DEGRADE_MARKER
        + 'Object.assign({},e,{promptVersion:"latest"}):e,t),useDsv3Harness:!1,'
        "agentTokenLimit:e.agentTokenLimit,estimatedCacheTtlMs:e.estimatedCacheTtlMs}}"
    )


DIRECT_STREAM_ANCHOR = (
    "function hre(e){return t=>{return n=this,o=void 0,s=function*(){"
)
AGENT_HOST_ENABLEMENT_RE = re.compile(
    r"(this\._agentHostEnabled=)([A-Za-z_$][A-Za-z0-9_$]*)(,)"
)
AGENT_HOST_ENABLEMENT_PATCH_RE = re.compile(
    rf"([A-Za-z_$][A-Za-z0-9_$]*)=!0;"
    rf"{re.escape(SAND_AGENT_HOST_ENABLEMENT_MARKER)}"
    rf"(this\._agentHostEnabled=)\1(,)"
)


def _validate_stream_transport(transport: str) -> str:
    if transport not in STREAM_TRANSPORTS:
        choices = ", ".join(STREAM_TRANSPORTS)
        raise SandToolError(f"不支持的推理传输模式：{transport}（可选：{choices}）")
    return transport


def _stream_transport_label(transport: Optional[str]) -> str:
    if transport == STREAM_TRANSPORT_SESSION:
        return "会话流"
    if transport == STREAM_TRANSPORT_DIRECT:
        return "直连流"
    return "未选择"


def _strip_dsv3_guard_patch_v1(content: str) -> Tuple[str, int]:
    """还原 V1 屏蔽掉的官方 useDsv3Harness 守卫。"""
    original_count = len(DSV3_LOCAL_LOOP_GUARD_RE.findall(content))
    patched_count = len(DSV3_LOCAL_LOOP_PATCHED_V1_RE.findall(content))
    marker_count = content.count(SAND_DSV3_LOCAL_LOOP_MARKER_V1)
    if marker_count == 0 and patched_count == 0:
        return content, 0
    if marker_count != 1 or patched_count != 1 or original_count != 0:
        raise SandToolError(
            "DSV3 旧版（V1）守卫补丁无法安全还原："
            f"original={original_count}, patched={patched_count}, marker={marker_count}"
        )

    def restore_guard(match: re.Match[str]) -> str:
        return (
            "if("
            + match.group("metadata")
            + ".useDsv3Harness)throw new "
            + match.group("error")
            + '("dsv3-harness-not-supported",'
            + match.group("model")
            + ");"
        )

    return DSV3_LOCAL_LOOP_PATCHED_V1_RE.subn(restore_guard, content, count=1)


def apply_dsv3_degrade_patch(content: str) -> Tuple[str, int]:
    """先剥掉 V1 守卫补丁，再在元数据解析处把 DSV3 模型降级到通用 harness（V2）。"""
    content, _stripped = _strip_dsv3_guard_patch_v1(content)
    original_count = len(DSV3_METADATA_RESOLVER_RE.findall(content))
    patched_count = len(DSV3_METADATA_DEGRADED_RE.findall(content))
    marker_count = content.count(SAND_DSV3_DEGRADE_MARKER)
    if marker_count == 1 and original_count == 0 and patched_count == 1:
        return content, 0
    if marker_count != 0 or patched_count != 0:
        raise SandToolError(
            "DSV3 降级补丁状态异常："
            f"original={original_count}, patched={patched_count}, marker={marker_count}"
        )
    if original_count == 0:
        return content, 0
    if original_count != 1:
        raise SandToolError(f"DSV3 元数据解析函数匹配异常：original={original_count}")
    return DSV3_METADATA_RESOLVER_RE.subn(
        lambda match: _dsv3_metadata_degraded(
            match.group("resolver"), match.group("info")
        ),
        content,
        count=1,
    )


def remove_dsv3_degrade_patch(content: str) -> Tuple[str, int]:
    """还原 V2 降级补丁；顺带清掉 V1 残留。"""
    content, stripped = _strip_dsv3_guard_patch_v1(content)
    original_count = len(DSV3_METADATA_RESOLVER_RE.findall(content))
    patched_count = len(DSV3_METADATA_DEGRADED_RE.findall(content))
    marker_count = content.count(SAND_DSV3_DEGRADE_MARKER)
    if marker_count == 0 and patched_count == 0:
        return content, stripped
    if marker_count != 1 or patched_count != 1 or original_count != 0:
        raise SandToolError(
            "DSV3 降级补丁无法安全还原："
            f"original={original_count}, patched={patched_count}, marker={marker_count}"
        )
    content, restored = DSV3_METADATA_DEGRADED_RE.subn(
        lambda match: _dsv3_metadata_original(
            match.group("resolver"), match.group("info")
        ),
        content,
        count=1,
    )
    return content, stripped + restored


def _direct_stream_injection() -> str:
    return (
        "{" + SAND_DIRECT_STREAM_MARKER + "const n=t.requestedModel;"
        'if(void 0===n)throw new Error("Sand direct Stream requires requestedModel");'
        'const o=String(n.modelId||""),i=o.toLowerCase(),'
        "r=new Map(n.parameters.map(e=>[e.id,e.value])),"
        "s=new Joe(e,n,void 0,void 0).getSession(),"
        "p={getExecutor:e=>new RK(s.getExecutor(e))},"
        'a={vendor:i.includes("grok")?"xai":i.includes("gemini")?"gemini":'
        'i.includes("claude")||i.includes("opus")||i.includes("sonnet")||i.includes("fable")?'
        '"anthropic":i.includes("gpt")||i.includes("codex")?"openai":"unknown",'
        'promptVersion:"latest",reasoningEffort:r.get("effort"),'
        'agentTokenLimit:(function(){const v=r.get("context");if(void 0===v)return void 0;const s=String(v).trim().toLowerCase();const n=parseFloat(s);if(!Number.isFinite(n)||n<=0)return void 0;const m=s.endsWith("k")?1e3:s.endsWith("m")?1e6:s.endsWith("b")?1e9:1;return n*m})(),'
        'isGrok45ProductPrompt:i.includes("grok"),'
        'isClaude4x:i.includes("claude")||i.includes("opus")||i.includes("sonnet")||i.includes("fable"),'
        'isFable5:i.includes("fable-5"),'
        'isOpus5:i.includes("opus-5")||i.includes("opus5"),'
        'isOpus48:i.includes("opus-4.8")||i.includes("opus48"),'
        'isOpus46:i.includes("opus-4.6")||i.includes("opus46"),'
        'isOpus45:i.includes("opus-4.5")||i.includes("opus45"),'
        'isSonnet45:i.includes("sonnet-4.5")||i.includes("sonnet45"),'
        'isSonnet4:i.includes("sonnet-4")||i.includes("sonnet4"),'
        'isGemini3:i.includes("gemini-3")||i.includes("gemini3"),'
        'isGpt56:i.includes("gpt-5.6")||i.includes("gpt5.6"),'
        'isGpt55:i.includes("gpt-5.5")||i.includes("gpt5.5"),'
        'isGpt54:i.includes("gpt-5.4")||i.includes("gpt5.4"),'
        'isGpt53Codex:i.includes("gpt-5.3-codex"),'
        'isGpt52Codex:i.includes("gpt-5.2-codex"),'
        'isCodexFamily:i.includes("codex"),isGpt5Family:i.includes("gpt-5")};'
        "return{promptSession:s,promptToolSession:p,attempt:{resolvedModel:cre(n),"
        "supportsSelfSummary:!1,routedModelDisplayName:o,"
        "resolvedModelMetadata:nre(a,o),finish:()=>Promise.resolve()}}}"
    )


def _platform_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    raise SandToolError("当前仅支持 Windows 和 macOS")


def _enable_windows_ansi() -> bool:
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):
            handle = kernel32.GetStdHandle(handle_id)
            if handle in (0, -1):
                continue
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                continue
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


def _configure_console() -> None:
    global _COLOR_ENABLED
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    if os.environ.get("NO_COLOR"):
        _COLOR_ENABLED = False
        return
    _COLOR_ENABLED = _enable_windows_ansi() and sys.stdout.isatty()


def colorize(text: str, *codes: str) -> str:
    if not _COLOR_ENABLED or not codes:
        return text
    return "".join(codes) + text + ANSI_RESET


def print_warn(text: str) -> None:
    print(colorize(text, ANSI_YELLOW))


def print_error(text: str) -> None:
    print(colorize(text, ANSI_RED), file=sys.stderr)


def print_success(text: str) -> None:
    print(colorize(text, ANSI_GREEN, ANSI_BOLD))


class LoadingSpinner:
    def __init__(self, message: str = "处理中") -> None:
        self.message = message
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self) -> "LoadingSpinner":
        if sys.stdout.isatty():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            print(colorize(self.message + "...", ANSI_BLUE), flush=True)
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            print("\r" + " " * 48 + "\r", end="", flush=True)

    def _run(self) -> None:
        frames = ("|", "/", "-", "\\")
        index = 0
        while not self._stop.wait(0.1):
            text = f"{frames[index % 4]} {self.message}"
            print("\r" + colorize(text, ANSI_BLUE), end="", flush=True)
            index += 1


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "SandClientModeStream" / "sand-client-cli"
        return (
            Path.home()
            / "AppData"
            / "Local"
            / "SandClientModeStream"
            / "sand-client-cli"
        )
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "SandClientModeStream"
            / "sand-client-cli"
        )
    return Path.home() / ".config" / "SandClientModeStream" / "sand-client-cli"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _path_key(path: Path) -> str:
    normalized = str(path.resolve())
    return os.path.normcase(normalized)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _product_checksum(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return base64.b64encode(digest).decode("ascii").rstrip("=")


def _atomic_write(path: Path, data: bytes, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / (
        f".{path.name}.sand-client-{os.getpid()}-{time.time_ns()}.tmp"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd: Optional[int] = None
    try:
        fd = os.open(str(temp), flags, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temp, stat.S_IMODE(mode))
        try:
            os.replace(temp, path)
        except PermissionError:
            original_mode: Optional[int] = None
            if path.exists():
                original_mode = stat.S_IMODE(path.stat().st_mode)
                os.chmod(path, original_mode | stat.S_IWRITE)
            try:
                os.replace(temp, path)
            except BaseException:
                if original_mode is not None and path.exists():
                    try:
                        os.chmod(path, original_mode)
                    except OSError:
                        pass
                raise
        if mode is not None:
            os.chmod(path, stat.S_IMODE(mode))
    finally:
        if fd is not None:
            os.close(fd)
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_write(path, data, 0o600)


def _load_config() -> Mapping[str, object]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SandToolError(
            f"配置文件损坏：{path}\n请运行 set-path auto 后重新检测"
        ) from exc
    if not isinstance(value, dict) or value.get("version") != CONFIG_VERSION:
        raise SandToolError(
            f"不支持的配置文件：{path}\n请运行 set-path auto 后重新检测"
        )
    return value


def _try_load_config() -> Dict[str, object]:
    try:
        return dict(_load_config())
    except SandToolError:
        return {}


def _identity_from_dict(raw: object) -> Optional[SpoofedIdentity]:
    if not isinstance(raw, Mapping):
        return None
    try:
        uuid_s = str(raw["rawMachineUuid"])
        mac = str(raw["macAddress"]).lower()
        dev = str(raw["devDeviceId"])
        sqm = str(raw.get("sqmId") or "")
    except (KeyError, TypeError):
        return None
    if not _UUID_RE.fullmatch(uuid_s) or not _UUID_RE.fullmatch(dev):
        return None
    if not _MAC_SPOOF_RE.fullmatch(mac):
        return None
    if sqm and not _SQM_RE.fullmatch(sqm):
        return None
    return SpoofedIdentity(
        raw_machine_uuid=uuid_s,
        machine_id=hashlib.sha256(uuid_s.encode("utf-8")).hexdigest(),
        mac_address=mac,
        mac_machine_id=hashlib.sha256(mac.encode("utf-8")).hexdigest(),
        dev_device_id=dev,
        sqm_id=sqm,
    )


def _generate_spoofed_identity() -> SpoofedIdentity:
    raw = str(uuid.uuid4())
    mac = "02:" + ":".join(f"{secrets.randbelow(256):02x}" for _ in range(5))
    sqm = "{" + str(uuid.uuid4()).upper() + "}" if sys.platform == "win32" else ""
    return SpoofedIdentity(
        raw_machine_uuid=raw,
        machine_id=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        mac_address=mac,
        mac_machine_id=hashlib.sha256(mac.encode("utf-8")).hexdigest(),
        dev_device_id=str(uuid.uuid4()),
        sqm_id=sqm,
    )


def _load_or_create_spoofed_identity() -> SpoofedIdentity:
    cfg = _try_load_config()
    ident = _identity_from_dict(cfg.get("spoofedIdentity"))
    if ident is not None:
        return ident
    ident = _generate_spoofed_identity()
    payload: Dict[str, object] = {
        "version": CONFIG_VERSION,
        "cursorInstallRoot": str(cfg.get("cursorInstallRoot") or ""),
        "lastVerifiedVersion": str(cfg.get("lastVerifiedVersion") or ""),
        "spoofedIdentity": ident.to_dict(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomic(_config_path(), payload)
    return ident


def _machine_id_k6_patched(raw_uuid: str) -> str:
    return (
        f'async function K6(e){{const t="{raw_uuid}"{SAND_MACHINE_ID_MARKER};'
        'let n;try{n=(await import("crypto")).createHash("sha256").update(t,"utf8").digest("hex")}'
        "catch{n=dt()}return e?t:n}"
    )


def _machine_mac_b9e_patched(mac: str) -> str:
    return f'function B9e(){{return"{mac}"{SAND_MACHINE_MAC_MARKER}}}'


def _machine_dev_z6_patched(dev_device_id: str) -> str:
    return f'async function z6(e){{return"{dev_device_id}"{SAND_MACHINE_DEV_MARKER}}}'


def _cursor_user_storage_path() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Cursor" / "User" / "globalStorage" / "storage.json"
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "globalStorage"
            / "storage.json"
        )
    return Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "storage.json"


def apply_spoofed_storage(identity: SpoofedIdentity) -> None:
    path = _cursor_user_storage_path()
    data: Dict[str, object] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SandToolError(f"无法读取 Cursor storage.json：{path}") from exc
        if isinstance(loaded, dict):
            data = loaded
    data["telemetry.machineId"] = identity.machine_id
    data["telemetry.macMachineId"] = identity.mac_machine_id
    data["telemetry.devDeviceId"] = identity.dev_device_id
    data["telemetry.sqmId"] = identity.sqm_id
    _write_json_atomic(path, data)
    machineid = path.parent.parent.parent / "machineid"
    try:
        _atomic_write(machineid, identity.dev_device_id.encode("utf-8"), 0o600)
    except OSError:
        pass


def storage_matches_identity(identity: SpoofedIdentity) -> Optional[bool]:
    path = _cursor_user_storage_path()
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(loaded, dict):
        return False
    return (
        loaded.get("telemetry.machineId") == identity.machine_id
        and loaded.get("telemetry.macMachineId") == identity.mac_machine_id
        and loaded.get("telemetry.devDeviceId") == identity.dev_device_id
        and loaded.get("telemetry.sqmId") == identity.sqm_id
    )


def _read_product(product_path: Path) -> Mapping[str, object]:
    try:
        size = product_path.stat().st_size
        if size <= 0 or size > 1024 * 1024:
            raise SandToolError(f"product.json 大小异常：{product_path}")
        raw = product_path.read_bytes()
        value = json.loads(raw.decode("utf-8-sig"))
    except SandToolError:
        raise
    except Exception as exc:
        raise SandToolError(f"无法读取 Cursor product.json：{product_path}") from exc
    if not isinstance(value, dict):
        raise SandToolError(f"Cursor product.json 格式错误：{product_path}")
    name = str(value.get("applicationName") or value.get("nameShort") or "")
    if name.casefold() != "cursor":
        raise SandToolError(f"所选目录不是 Cursor 安装：{product_path}")
    return value


def _find_app_bundle(app_root: Path) -> Optional[Path]:
    for item in (app_root, *app_root.parents):
        if item.name.casefold() == "cursor.app":
            return item
    return None


def _candidate_app_roots(raw_path: Path) -> Iterable[Path]:
    path = raw_path
    if path.is_file():
        if path.name.casefold() == "product.json":
            path = path.parent
        else:
            path = path.parent
    current = path
    for _ in range(8):
        yield current
        yield current / "resources" / "app"
        yield current / "Resources" / "app"
        yield current / "Contents" / "Resources" / "app"
        if current.parent == current:
            break
        current = current.parent


def _resolve_executable(app_root: Path) -> Tuple[Path, Path]:
    if sys.platform == "win32":
        if app_root.parent.name.casefold() == "resources":
            install_root = app_root.parent.parent
        else:
            install_root = app_root
        candidates = (
            install_root / "Cursor.exe",
            install_root / "cursor.exe",
        )
    elif sys.platform == "darwin":
        bundle = _find_app_bundle(app_root)
        if bundle is None:
            raise SandToolError("macOS Cursor 路径必须位于 Cursor.app 内")
        install_root = bundle
        candidates = (bundle / "Contents" / "MacOS" / "Cursor",)
    else:
        raise SandToolError("当前仅支持 Windows 和 macOS")

    for executable in candidates:
        try:
            resolved = executable.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        if resolved.is_file() and _is_within(resolved, install_root.resolve()):
            return install_root.resolve(), resolved
    raise SandToolError(f"未找到 Cursor 可执行文件：{install_root}")


def layout_from_path(value: Union[str, Path]) -> CursorLayout:
    raw_text = str(value).strip().strip('"')
    if not raw_text:
        raise SandToolError("Cursor 路径不能为空")
    if sys.platform == "win32" and (
        raw_text.startswith("\\\\") or raw_text.startswith("\\\\?\\")
    ):
        raise SandToolError("不支持 UNC 或 Windows 设备路径")

    raw = Path(raw_text).expanduser()
    if not raw.is_absolute():
        raise SandToolError(f"Cursor 路径必须是绝对路径：{raw}")
    try:
        raw = raw.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise SandToolError(f"Cursor 路径不存在：{raw}") from exc

    seen: Set[str] = set()
    last_error: Optional[Exception] = None
    for candidate in _candidate_app_roots(raw):
        try:
            app_root = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        key = _path_key(app_root)
        if key in seen:
            continue
        seen.add(key)

        product_json = app_root / "product.json"
        if not product_json.is_file():
            continue
        try:
            product_real = product_json.resolve(strict=True)
            if not _is_within(product_real, app_root):
                raise SandToolError("product.json 符号链接逃逸出 Cursor app 目录")
            product = _read_product(product_real)
            install_root, executable = _resolve_executable(app_root)

            targets: List[Path] = []
            for rel, _extension_name in TARGET_SPECS:
                target = app_root.joinpath(*rel.split("/"))
                if not target.is_file():
                    continue
                target_real = target.resolve(strict=True)
                if not _is_within(target_real, app_root):
                    raise SandToolError(f"目标文件符号链接逃逸：{target}")
                targets.append(target_real)
            if not targets:
                raise SandToolError(
                    "Cursor 使用 app.asar 或当前版本没有可识别的 Sand 目标文件"
                )

            ext_host = app_root.joinpath(*EXT_HOST_REL.split("/"))
            ext_host_real = (
                ext_host.resolve(strict=True) if ext_host.is_file() else None
            )
            version = str(product.get("version") or product.get("commit") or "未知")
            return CursorLayout(
                install_root=install_root,
                app_root=app_root,
                product_json=product_real,
                executable=executable,
                target_paths=tuple(targets),
                ext_host_path=ext_host_real,
                version=version,
            )
        except SandToolError as exc:
            last_error = exc
            continue

    if last_error:
        raise SandToolError(f"Cursor 路径校验失败：{last_error}") from last_error
    raise SandToolError(f"路径中未找到 Cursor resources/app：{raw}")


def _powershell_executable() -> Optional[str]:
    return (
        shutil.which("powershell.exe")
        or shutil.which("powershell")
        or shutil.which("pwsh")
    )


def _windows_running_candidates() -> List[str]:
    powershell = _powershell_executable()
    if not powershell:
        return []
    script = (
        "$ErrorActionPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();"
        "Get-CimInstance Win32_Process -Filter \"Name='Cursor.exe'\" | "
        "ForEach-Object { if ($_.ExecutablePath) { $_.ExecutablePath } }"
    )
    try:
        result = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _windows_registry_candidates() -> List[str]:
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except ImportError:
        return []

    candidates: List[str] = []
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    uninstall = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for root in roots:
        for view in views:
            try:
                parent = winreg.OpenKey(root, uninstall, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with parent:
                index = 0
                while True:
                    try:
                        name = winreg.EnumKey(parent, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        child = winreg.OpenKey(parent, name)
                    except OSError:
                        continue
                    with child:

                        def read(name_: str) -> str:
                            try:
                                return str(winreg.QueryValueEx(child, name_)[0] or "")
                            except OSError:
                                return ""

                        display_name = read("DisplayName").strip()
                        publisher = read("Publisher").strip()
                        if (
                            display_name.casefold() != "cursor"
                            and "anysphere" not in publisher.casefold()
                        ):
                            continue
                        install_location = read("InstallLocation").strip().strip('"')
                        display_icon = read("DisplayIcon").strip().strip('"')
                        if install_location:
                            candidates.append(install_location)
                        if display_icon:
                            icon_path = re.sub(r",\s*-?\d+$", "", display_icon).strip(
                                '"'
                            )
                            candidates.append(icon_path)
    return candidates


def _mac_process_paths(strict: bool = False) -> List[Tuple[int, Path]]:
    try:
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
        proc_pidpath = libproc.proc_pidpath
        proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        proc_pidpath.restype = ctypes.c_int
        result = subprocess.run(
            ["ps", "-axo", "pid="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if strict:
            raise SandToolError("无法读取 macOS 进程可执行路径") from exc
        return []
    if result.returncode != 0:
        if strict:
            raise SandToolError("无法读取 macOS 进程可执行路径")
        return []
    values: List[Tuple[int, Path]] = []
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        buffer = ctypes.create_string_buffer(4096)
        length = proc_pidpath(pid, buffer, len(buffer))
        if length <= 0:
            continue
        try:
            executable = Path(os.fsdecode(buffer.value)).resolve(strict=False)
        except (OSError, ValueError):
            continue
        values.append((pid, executable))
    return values


def _bundle_for_executable(executable: Path) -> Optional[Path]:
    for item in (executable, *executable.parents):
        if item.name.casefold() == "cursor.app":
            return item
    return None


def _mac_running_candidates() -> List[str]:
    values: Dict[str, str] = {}
    for _pid, executable in _mac_process_paths():
        bundle = _bundle_for_executable(executable)
        if bundle is not None:
            values.setdefault(_path_key(bundle), str(bundle))
    return list(values.values())


def _mac_spotlight_candidates() -> List[str]:
    mdfind = shutil.which("mdfind")
    if not mdfind:
        return []
    try:
        result = subprocess.run(
            [
                mdfind,
                "kMDItemCFBundleIdentifier == 'com.todesktop.230313mzl4w4u92'",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _default_candidate_groups() -> Iterable[Tuple[str, Sequence[str]]]:
    env_candidate = os.environ.get("SAND_CURSOR_INSTALL_DIR", "").strip()
    if env_candidate:
        yield "环境变量 SAND_CURSOR_INSTALL_DIR", (env_candidate,)

    if sys.platform == "win32":
        yield "运行中的 Cursor", _windows_running_candidates()
        yield "Windows 安装登记", _windows_registry_candidates()
        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
        defaults = [
            str(Path(local) / "Programs" / "Cursor") if local else "",
            str(Path(local) / "Programs" / "cursor") if local else "",
            str(Path(local) / "Cursor") if local else "",
            str(Path(program_files) / "Cursor"),
            str(Path(program_files_x86) / "Cursor") if program_files_x86 else "",
        ]
        yield "Windows 默认目录", tuple(x for x in defaults if x)
    elif sys.platform == "darwin":
        yield "运行中的 Cursor", _mac_running_candidates()
        yield "macOS Spotlight", _mac_spotlight_candidates()
        yield (
            "macOS 默认目录",
            (
                "/Applications/Cursor.app",
                str(Path.home() / "Applications" / "Cursor.app"),
            ),
        )

    path_cursor = shutil.which("cursor")
    if path_cursor:
        yield "PATH", (path_cursor,)


def _valid_layouts(values: Sequence[str]) -> List[CursorLayout]:
    layouts: Dict[str, CursorLayout] = {}
    for value in values:
        if not value:
            continue
        try:
            layout = layout_from_path(value)
        except SandToolError:
            continue
        layouts.setdefault(_path_key(layout.app_root), layout)
    return list(layouts.values())


def resolve_cursor_layout() -> CursorLayout:
    configured = _load_config().get("cursorInstallRoot")
    if isinstance(configured, str) and configured.strip():
        try:
            return layout_from_path(configured)
        except SandToolError as exc:
            raise SandToolError(
                f"已设置的 Cursor 路径失效：{configured}\n"
                "请运行 set-path <新路径>，或运行 set-path auto 恢复自动检测"
            ) from exc

    for source, values in _default_candidate_groups():
        layouts = _valid_layouts(tuple(values))
        if len(layouts) == 1:
            return layouts[0]
        if len(layouts) > 1:
            options = "\n".join(f"  - {item.install_root}" for item in layouts)
            raise SandToolError(
                f"{source}检测到多个 Cursor 安装，请先在菜单中选择 3 设置路径：\n{options}"
            )
    raise SandToolError(
        "未检测到 Cursor 安装，请在菜单中选择 3 设置 Cursor 路径"
        "（Cursor.exe、Cursor.app 或 resources/app）"
    )


def save_cursor_path(value: str) -> Optional[CursorLayout]:
    existing = _try_load_config()
    identity = existing.get("spoofedIdentity")
    payload: Dict[str, object] = {
        "version": CONFIG_VERSION,
        "cursorInstallRoot": "",
        "lastVerifiedVersion": "",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if isinstance(identity, dict):
        payload["spoofedIdentity"] = identity

    if value.strip().casefold() in {"auto", "clear", "reset"}:
        _write_json_atomic(_config_path(), payload)
        return None

    layout = layout_from_path(value)
    payload["cursorInstallRoot"] = str(layout.install_root)
    payload["lastVerifiedVersion"] = layout.version
    _write_json_atomic(_config_path(), payload)
    return layout


def _strip_legacy_rules_skills(content: str) -> Tuple[str, bool, int]:
    """剥掉 host 侧 V1–V3。标记还在但整串对不上时原样返回并 ok=False。"""
    next_content = content
    removed = 0
    for marker, payload in _RULES_SKILLS_LEGACY_PAYLOADS:
        if marker not in next_content:
            continue
        if payload not in next_content:
            return content, False, 0
        next_content = next_content.replace(payload, RULES_SKILLS_HOST_ORIGINAL, 1)
        removed += 1
    return next_content, True, removed


def apply_patch_to_content(
    content: str,
    transport: str = STREAM_TRANSPORT_SESSION,
    identity: Optional[SpoofedIdentity] = None,
) -> Tuple[str, PatchStats]:
    transport = _validate_stream_transport(transport)
    stats = PatchStats()
    next_content = content
    legacy_client_re = re.compile(rf"([\"'])sand\1{LEGACY_CLIENT_MARKER_PATTERN}")
    next_content, stats.migrated_client = legacy_client_re.subn(
        lambda match: match.group(1) + "sand" + match.group(1) + SAND_CLIENT_MARKER,
        next_content,
    )
    legacy_eligibility = "return!1;" + LEGACY_SAND_ELIGIBILITY_MARKER
    stats.migrated_eligibility = next_content.count(legacy_eligibility)
    next_content = next_content.replace(
        legacy_eligibility,
        "return!1;" + SAND_ELIGIBILITY_MARKER,
    )
    for key, rule in CLIENT_RULES:

        def replace_client(match: re.Match[str], stat_key: str = key) -> str:
            current = match.group(3)
            setattr(stats, stat_key, getattr(stats, stat_key) + 1)
            if current == "sand":
                stats.adopted_sand += 1
                marker = SAND_CLIENT_EXISTING_MARKER
            else:
                marker = SAND_CLIENT_MARKER
            return match.group(1) + match.group(2) + "sand" + match.group(2) + marker

        next_content = rule.sub(replace_client, next_content)

    for prefix in ELIGIBILITY_PREFIXES:
        count = next_content.count(prefix)
        if count == 0:
            continue
        patched = prefix.replace(
            "{const{adminSettingsService:",
            "{return!1;" + SAND_ELIGIBILITY_MARKER + "const{adminSettingsService:",
        )
        next_content = next_content.replace(prefix, patched)
        stats.eligibility += count

    route_count = next_content.count(MANAGED_LOCAL_ROUTE_ORIGINAL)
    if route_count:
        next_content = next_content.replace(
            MANAGED_LOCAL_ROUTE_ORIGINAL,
            MANAGED_LOCAL_ROUTE_PATCHED,
        )
        stats.managed_local_route += route_count

    runtime_load_count = next_content.count(LOCAL_RUNTIME_LOAD_ORIGINAL)
    if runtime_load_count:
        next_content = next_content.replace(
            LOCAL_RUNTIME_LOAD_ORIGINAL,
            LOCAL_RUNTIME_LOAD_PATCHED,
        )
        stats.local_runtime_load += runtime_load_count

    identity_count = next_content.count(AGENT_HOST_IDENTITY_ORIGINAL)
    if identity_count:
        next_content = next_content.replace(
            AGENT_HOST_IDENTITY_ORIGINAL,
            AGENT_HOST_IDENTITY_PATCHED,
        )
        stats.agent_host_identity += identity_count

    next_content, dsv3_count = apply_dsv3_degrade_patch(next_content)
    stats.dsv3_local_loop += dsv3_count

    # 会话流只打标记，保留原生 runInference，网页 Usage 才会记到 bot/free。
    # 直连流自建 Joe session，会绕开这条计费链，只作兼容回退。
    direct_injection = _direct_stream_injection()
    if transport == STREAM_TRANSPORT_SESSION:
        if direct_injection in next_content:
            next_content = next_content.replace(direct_injection, "", 1)
        session_marker_count = next_content.count(SAND_SESSION_STREAM_MARKER)
        if session_marker_count > 1:
            raise SandToolError(
                f"原生会话 Stream marker 数量异常：{session_marker_count}"
            )
        if session_marker_count == 0 and DIRECT_STREAM_ANCHOR in next_content:
            next_content = next_content.replace(
                DIRECT_STREAM_ANCHOR,
                DIRECT_STREAM_ANCHOR + SAND_SESSION_STREAM_MARKER,
                1,
            )
            stats.session_stream += 1
    else:
        session_marker_count = next_content.count(SAND_SESSION_STREAM_MARKER)
        if session_marker_count > 1:
            raise SandToolError(
                f"原生会话 Stream marker 数量异常：{session_marker_count}"
            )
        if session_marker_count == 1:
            next_content = next_content.replace(SAND_SESSION_STREAM_MARKER, "", 1)
        if (
            SAND_DIRECT_STREAM_MARKER not in next_content
            and DIRECT_STREAM_ANCHOR in next_content
        ):
            next_content = next_content.replace(
                DIRECT_STREAM_ANCHOR,
                DIRECT_STREAM_ANCHOR + direct_injection,
                1,
            )
            stats.direct_stream += 1

    if SAND_AGENT_HOST_ENABLEMENT_MARKER not in next_content:

        def enable_agent_host(match: re.Match[str]) -> str:
            variable = match.group(2)
            return (
                variable
                + "=!0;"
                + SAND_AGENT_HOST_ENABLEMENT_MARKER
                + match.group(1)
                + variable
                + match.group(3)
            )

        next_content, agent_host_count = AGENT_HOST_ENABLEMENT_RE.subn(
            enable_agent_host,
            next_content,
            count=1,
        )
        stats.agent_host_enablement += agent_host_count

    # move-exec 强制 ON：修复 managed-local 下工具执行器缺失
    if SAND_MOVE_EXEC_MARKER not in next_content:
        if MOVE_EXEC_ORIGINAL in next_content:
            next_content = next_content.replace(
                MOVE_EXEC_ORIGINAL, MOVE_EXEC_PATCHED, 1
            )
            stats.move_exec += 1

    # 子 agent Task 工具激活（675.js）
    if SAND_TASK_TOOL_MARKER not in next_content:
        if TASK_TOOL_ORIGINAL in next_content:
            next_content = next_content.replace(
                TASK_TOOL_ORIGINAL, TASK_TOOL_PATCHED, 1
            )
            stats.task_tool += 1

    # 子 agent 走 client-side 本地路径（675.js）
    if SAND_CLIENT_SIDE_SUBAGENT_MARKER not in next_content:
        if CLIENT_SIDE_SUBAGENT_ORIGINAL in next_content:
            next_content = next_content.replace(
                CLIENT_SIDE_SUBAGENT_ORIGINAL, CLIENT_SIDE_SUBAGENT_PATCHED, 1
            )
            stats.client_side_subagent += 1

    # 子 agent turn 放行（657.js）：isSubagentTurn 字段
    if SUBAGENT_TURN_N_NEW not in next_content:
        if SUBAGENT_TURN_N_OLD in next_content:
            next_content = next_content.replace(
                SUBAGENT_TURN_N_OLD, SUBAGENT_TURN_N_NEW, 1
            )
            stats.subagent_turn += 1

    # 子 agent / Plan Build 路由短路（657.js）：followup、turn、
    # executePlanAction、resumeAction 走 managed-local。
    if SAND_PLAN_BUILD_MARKER not in next_content:
        if SUBAGENT_ROUTE_PATCHED_V1 in next_content:
            next_content = next_content.replace(
                SUBAGENT_ROUTE_PATCHED_V1, SUBAGENT_ROUTE_PATCHED, 1
            )
            stats.subagent_turn += 1
        elif SUBAGENT_ROUTE_ORIGINAL in next_content:
            next_content = next_content.replace(
                SUBAGENT_ROUTE_ORIGINAL, SUBAGENT_ROUTE_PATCHED, 1
            )
            stats.subagent_turn += 1

    # 放行所有 Agent 模式（Ask/Plan/Debug/Multitask）走 managed-local（657.js）
    if SAND_MODE_RELAX_MARKER not in next_content:
        if MODE_RELAX_ORIGINAL in next_content:
            next_content = next_content.replace(
                MODE_RELAX_ORIGINAL, MODE_RELAX_PATCHED, 1
            )
            stats.subagent_turn += 1

    # 上下文窗口 maxTokens 覆盖（675.js）：后端按默认档返回，用 context 参数覆盖
    if SAND_MAX_TOKENS_MARKER not in next_content:
        if MAX_TOKENS_ORIGINAL in next_content:
            next_content = next_content.replace(
                MAX_TOKENS_ORIGINAL, MAX_TOKENS_PATCHED, 1
            )
            stats.task_tool += 1

    # 首字(TTFT)延迟优化（workbench.desktop.main.js）：buildFromPushedData
    # 等待 pushed rules 的超时 10s → 1s。多版本锚点 yCd(3.18.25)/Ykd(3.18.9)。
    if SAND_TTFT_MARKER not in next_content:
        for original in TTFT_ORIGINALS:
            if next_content.count(original) == 1:
                patched_text = original.replace("=1e4", "=1e3") + SAND_TTFT_MARKER
                next_content = next_content.replace(original, patched_text, 1)
                stats.ttft += 1
                break

    # Rules/Skills 恢复（cursor-agent-exec/dist/main.js）：host 启用时 aa() 跳过 na()。
    # 先剥掉 host 侧 V1–V3 旧注入，再改 aa() 补调 na()。
    next_content, legacy_ok, _removed = _strip_legacy_rules_skills(next_content)
    if SAND_RULES_SKILLS_MARKER not in next_content:
        if legacy_ok and next_content.count(RULES_SKILLS_EXEC_ORIGINAL) == 1:
            next_content = next_content.replace(
                RULES_SKILLS_EXEC_ORIGINAL, RULES_SKILLS_EXEC_PATCHED, 1
            )
            stats.rules_skills += 1

    # User Rules 注入（workbench.desktop.main.js）：injectLocalModeNonFileRules 去掉
    # localMode 守卫，managed-local 也把 Settings 里的 User/Team rules 并进 requestContext。
    if SAND_USER_RULES_MARKER not in next_content:
        if len(USER_RULES_ORIGINAL_RE.findall(next_content)) == 1:
            next_content, user_rules_count = USER_RULES_ORIGINAL_RE.subn(
                lambda match: (
                    "injectLocalModeNonFileRules(e){if(!1&&!"
                    + match.group("flags")
                    + ".localMode)return;"
                    + SAND_USER_RULES_MARKER
                ),
                next_content,
                count=1,
            )
            stats.user_rules += user_rules_count

    # MCP FileSystem 提示块（675.js）：不再依赖服务端下发的 enableMCPFileSystem，
    # 让 <mcp_file_system> 始终进 system prompt，agent 才知道去 <projectDir>/mcps 找 server。
    if SAND_MCP_FILESYSTEM_MARKER not in next_content:
        if next_content.count(MCP_FILESYSTEM_ORIGINAL) == 1:
            next_content = next_content.replace(
                MCP_FILESYSTEM_ORIGINAL, MCP_FILESYSTEM_PATCHED, 1
            )
            stats.mcp_filesystem += 1

    # 同一 turn 多次交互串号修复（657.js）：主会话 query 也带 seq。
    if SAND_INTERACTION_SEQ_MARKER not in next_content:
        if len(INTERACTION_SEQ_ORIGINAL_RE.findall(next_content)) == 1:
            next_content, seq_count = INTERACTION_SEQ_ORIGINAL_RE.subn(
                lambda match: _interaction_seq_patched(match.group("awaiter")),
                next_content,
                count=1,
            )
            stats.interaction_seq += seq_count

    # 机器码伪装（out/main.js）：K6 硬件 UUID、B9e MAC。uninstall 不还原。
    if SAND_MACHINE_ID_MARKER not in next_content:
        if next_content.count(MACHINE_ID_K6_ORIGINAL) == 1:
            ident = identity or _load_or_create_spoofed_identity()
            next_content = next_content.replace(
                MACHINE_ID_K6_ORIGINAL,
                _machine_id_k6_patched(ident.raw_machine_uuid),
                1,
            )
            stats.machine_id += 1
    if SAND_MACHINE_MAC_MARKER not in next_content:
        if next_content.count(MACHINE_MAC_B9E_ORIGINAL) == 1:
            ident = identity or _load_or_create_spoofed_identity()
            next_content = next_content.replace(
                MACHINE_MAC_B9E_ORIGINAL,
                _machine_mac_b9e_patched(ident.mac_address),
                1,
            )
            stats.machine_mac += 1
    if SAND_MACHINE_DEV_MARKER not in next_content:
        if next_content.count(MACHINE_DEV_Z6_ORIGINAL) == 1:
            ident = identity or _load_or_create_spoofed_identity()
            next_content = next_content.replace(
                MACHINE_DEV_Z6_ORIGINAL,
                _machine_dev_z6_patched(ident.dev_device_id),
                1,
            )
            stats.machine_dev += 1
    return next_content, stats


def remove_machine_id_from_content(content: str) -> Tuple[str, int]:
    """显式还原 K6/B9e/z6。普通 uninstall 不调用，避免真实机器码再次上传。"""
    next_content, k6_count = MACHINE_ID_K6_PATCHED_RE.subn(
        MACHINE_ID_K6_ORIGINAL, content, count=1
    )
    next_content, mac_count = MACHINE_MAC_B9E_PATCHED_RE.subn(
        MACHINE_MAC_B9E_ORIGINAL, next_content, count=1
    )
    next_content, dev_count = MACHINE_DEV_Z6_PATCHED_RE.subn(
        MACHINE_DEV_Z6_ORIGINAL, next_content, count=1
    )
    return next_content, k6_count + mac_count + dev_count


def remove_patch_from_content(content: str) -> Tuple[str, RemoveStats]:
    stats = RemoveStats()
    legacy_client_re = re.compile(rf"([\"'])sand\1{LEGACY_CLIENT_MARKER_PATTERN}")
    next_content, legacy_client_count = legacy_client_re.subn(
        lambda match: match.group(1) + "ide" + match.group(1),
        content,
    )
    stats.client_type += legacy_client_count
    legacy_eligibility = "return!1;" + LEGACY_SAND_ELIGIBILITY_MARKER
    legacy_eligibility_count = next_content.count(legacy_eligibility)
    next_content = next_content.replace(legacy_eligibility, "")
    stats.eligibility += legacy_eligibility_count
    client_re = re.compile(rf"([\"'])sand\1{CLIENT_MARKER_PATTERN}")
    existing_re = re.compile(rf"([\"'])sand\1{CLIENT_EXISTING_MARKER_PATTERN}")

    def remove_client(match: re.Match[str]) -> str:
        stats.client_type += 1
        return match.group(1) + "ide" + match.group(1)

    next_content = client_re.sub(remove_client, next_content)
    next_content, existing_count = existing_re.subn(
        lambda match: match.group(1) + "sand" + match.group(1),
        next_content,
    )
    stats.client_type += existing_count
    eligibility_re = re.compile(rf"return!1;{ELIGIBILITY_MARKER_PATTERN}")
    next_content, eligibility_count = eligibility_re.subn("", next_content)
    stats.eligibility += eligibility_count

    route_count = next_content.count(MANAGED_LOCAL_ROUTE_PATCHED)
    if route_count:
        next_content = next_content.replace(
            MANAGED_LOCAL_ROUTE_PATCHED,
            MANAGED_LOCAL_ROUTE_ORIGINAL,
        )
        stats.managed_local_route += route_count

    runtime_load_count = next_content.count(LOCAL_RUNTIME_LOAD_PATCHED)
    if runtime_load_count:
        next_content = next_content.replace(
            LOCAL_RUNTIME_LOAD_PATCHED,
            LOCAL_RUNTIME_LOAD_ORIGINAL,
        )
        stats.local_runtime_load += runtime_load_count

    identity_count = next_content.count(AGENT_HOST_IDENTITY_PATCHED)
    if identity_count:
        next_content = next_content.replace(
            AGENT_HOST_IDENTITY_PATCHED,
            AGENT_HOST_IDENTITY_ORIGINAL,
        )
        stats.agent_host_identity += identity_count

    session_count = next_content.count(SAND_SESSION_STREAM_MARKER)
    if session_count:
        next_content = next_content.replace(SAND_SESSION_STREAM_MARKER, "")
        stats.session_stream += session_count

    direct_injection = _direct_stream_injection()
    direct_count = next_content.count(direct_injection)
    if direct_count:
        next_content = next_content.replace(direct_injection, "")
        stats.direct_stream += direct_count

    next_content, dsv3_count = remove_dsv3_degrade_patch(next_content)
    stats.dsv3_local_loop += dsv3_count

    next_content, agent_host_count = AGENT_HOST_ENABLEMENT_PATCH_RE.subn(
        lambda match: match.group(2) + match.group(1) + match.group(3),
        next_content,
    )
    stats.agent_host_enablement += agent_host_count
    if MOVE_EXEC_PATCHED in next_content:
        next_content = next_content.replace(MOVE_EXEC_PATCHED, MOVE_EXEC_ORIGINAL, 1)
        stats.move_exec += 1
    if SAND_SUBAGENT_TURN_MARKER in next_content:
        if SUBAGENT_ROUTE_PATCHED in next_content:
            next_content = next_content.replace(
                SUBAGENT_ROUTE_PATCHED, SUBAGENT_ROUTE_ORIGINAL, 1
            )
            stats.subagent_turn += 1
        elif SUBAGENT_ROUTE_PATCHED_V1 in next_content:
            next_content = next_content.replace(
                SUBAGENT_ROUTE_PATCHED_V1, SUBAGENT_ROUTE_ORIGINAL, 1
            )
            stats.subagent_turn += 1
    if SAND_MODE_RELAX_MARKER in next_content:
        if MODE_RELAX_PATCHED in next_content:
            next_content = next_content.replace(
                MODE_RELAX_PATCHED, MODE_RELAX_ORIGINAL, 1
            )
            stats.subagent_turn += 1
    if SUBAGENT_TURN_N_NEW in next_content:
        next_content = next_content.replace(SUBAGENT_TURN_N_NEW, SUBAGENT_TURN_N_OLD, 1)
        stats.subagent_turn += 1
    if SAND_CLIENT_SIDE_SUBAGENT_MARKER in next_content:
        if CLIENT_SIDE_SUBAGENT_PATCHED in next_content:
            next_content = next_content.replace(
                CLIENT_SIDE_SUBAGENT_PATCHED, CLIENT_SIDE_SUBAGENT_ORIGINAL, 1
            )
            stats.client_side_subagent += 1
    if SAND_TASK_TOOL_MARKER in next_content:
        if TASK_TOOL_PATCHED in next_content:
            next_content = next_content.replace(
                TASK_TOOL_PATCHED, TASK_TOOL_ORIGINAL, 1
            )
            stats.task_tool += 1
    if SAND_MAX_TOKENS_MARKER in next_content:
        if MAX_TOKENS_PATCHED in next_content:
            next_content = next_content.replace(
                MAX_TOKENS_PATCHED, MAX_TOKENS_ORIGINAL, 1
            )
            stats.task_tool += 1
    if SAND_TTFT_MARKER in next_content:
        next_content, ttft_count = TTFT_RESTORE_RE.subn(
            lambda match: match.group(1) + "=1e4",
            next_content,
            count=1,
        )
        stats.ttft += ttft_count
    if SAND_RULES_SKILLS_MARKER in next_content:
        if RULES_SKILLS_EXEC_PATCHED in next_content:
            next_content = next_content.replace(
                RULES_SKILLS_EXEC_PATCHED, RULES_SKILLS_EXEC_ORIGINAL, 1
            )
            stats.rules_skills += 1
    next_content, _legacy_ok, legacy_removed = _strip_legacy_rules_skills(next_content)
    stats.rules_skills += legacy_removed
    if SAND_USER_RULES_MARKER in next_content:
        next_content, user_rules_count = USER_RULES_PATCHED_RE.subn(
            lambda match: (
                "injectLocalModeNonFileRules(e){if(!"
                + match.group("flags")
                + ".localMode)return;"
            ),
            next_content,
            count=1,
        )
        stats.user_rules += user_rules_count
    if SAND_MCP_FILESYSTEM_MARKER in next_content:
        if MCP_FILESYSTEM_PATCHED in next_content:
            next_content = next_content.replace(
                MCP_FILESYSTEM_PATCHED, MCP_FILESYSTEM_ORIGINAL, 1
            )
            stats.mcp_filesystem += 1
    if SAND_INTERACTION_SEQ_MARKER in next_content:
        next_content, seq_count = INTERACTION_SEQ_PATCHED_RE.subn(
            lambda match: _interaction_seq_original(match.group("awaiter")),
            next_content,
            count=1,
        )
        stats.interaction_seq += seq_count
    return next_content, stats


def _decode_js(data: bytes, path: Path) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SandToolError(f"目标文件不是 UTF-8，拒绝修改：{path}") from exc


def _read_planned_file(path: Path) -> PlannedFile:
    original = path.read_bytes()
    return PlannedFile(
        original=original,
        next_bytes=original,
        mode=stat.S_IMODE(path.stat().st_mode),
    )


def _target_extension_name(layout: CursorLayout, file_path: Path) -> Optional[str]:
    for rel, extension_name in TARGET_SPECS:
        if not extension_name:
            continue
        candidate = layout.app_root.joinpath(*rel.split("/")).resolve()
        if candidate == file_path.resolve():
            return extension_name
    return None


def _update_extension_hashes(
    layout: CursorLayout,
    plan: Dict[Path, PlannedFile],
) -> None:
    changed_extensions: List[Tuple[str, bytes]] = []
    for file_path, planned in plan.items():
        extension_name = _target_extension_name(layout, file_path)
        if extension_name:
            changed_extensions.append((extension_name, planned.next_bytes))
    if not changed_extensions or layout.ext_host_path is None:
        return

    ext_path = layout.ext_host_path
    existing = plan.get(ext_path) or _read_planned_file(ext_path)
    next_content = _decode_js(existing.next_bytes, ext_path)
    original_content = _decode_js(existing.original, ext_path)

    for extension_name, next_main in changed_extensions:
        extension_id = "anysphere." + extension_name
        if f'"{extension_id}"' not in next_content:
            continue
        digest = hashlib.sha256(next_main).hexdigest()
        pattern = re.compile(
            rf"(\"{re.escape(extension_id)}\"\s*:\s*\{{[\s\S]{{0,2400}}?"
            rf"\"main\.js\"\s*:\s*\")[0-9a-f]{{64}}(\")"
        )
        next_content, count = pattern.subn(
            lambda match: match.group(1) + digest + match.group(2),
            next_content,
            count=1,
        )
        if count > 1:
            raise SandToolError(f"{extension_id} 的内嵌 main.js 哈希不唯一")

    if next_content != original_content:
        plan[ext_path] = PlannedFile(
            original=existing.original,
            next_bytes=next_content.encode("utf-8"),
            mode=existing.mode,
        )


def _sync_product_checksums(
    layout: CursorLayout,
    plan: Dict[Path, PlannedFile],
) -> None:
    product_file = _read_planned_file(layout.product_json)
    has_bom = product_file.original.startswith(b"\xef\xbb\xbf")
    try:
        product = json.loads(product_file.original.decode("utf-8-sig"))
    except Exception as exc:
        raise SandToolError("product.json 无法解析，拒绝提交补丁") from exc
    if not isinstance(product, dict):
        raise SandToolError("product.json 顶层必须是对象")
    checksums = product.get("checksums")
    if not isinstance(checksums, dict):
        return

    out_root = (layout.app_root / "out").resolve()
    changed = False
    for key in list(checksums.keys()):
        if not isinstance(key, str):
            continue
        parts = [part for part in re.split(r"[\\/]", key) if part]
        target = out_root.joinpath(*parts).resolve()
        if not _is_within(target, out_root):
            raise SandToolError(f"product.json checksum 路径逃逸：{key}")
        planned = plan.get(target)
        if planned is not None:
            data = planned.next_bytes
        elif target.is_file():
            data = target.read_bytes()
        else:
            continue
        digest = _product_checksum(data)
        if checksums.get(key) != digest:
            checksums[key] = digest
            changed = True

    if not changed:
        return
    text = json.dumps(product, ensure_ascii=False, indent="\t")
    next_bytes = text.encode("utf-8")
    if has_bom:
        next_bytes = b"\xef\xbb\xbf" + next_bytes
    plan[layout.product_json] = PlannedFile(
        original=product_file.original,
        next_bytes=next_bytes,
        mode=product_file.mode,
    )


def _sync_checksum_for_target(layout: CursorLayout, target: Path) -> None:
    """把 product.json 里 target 对应 key 的 checksum 刷新为磁盘当前值。

    用于独立补丁（ttft 等）绕过 plan 体系直接改写 out/ 下的 bundle 后，
    同步 product.json 完整性校验，避免 Cursor 启动报 "corrupt"。
    """
    product_file = layout.product_json
    raw = product_file.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        product = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise SandToolError("product.json 无法解析，无法同步 checksum") from exc
    if not isinstance(product, dict):
        return
    checksums = product.get("checksums")
    if not isinstance(checksums, dict):
        return

    out_root = (layout.app_root / "out").resolve()
    if not _is_within(target, out_root):
        return
    resolved_target = target.resolve()
    changed = False
    for key in list(checksums.keys()):
        if not isinstance(key, str):
            continue
        parts = [part for part in re.split(r"[\\/]", key) if part]
        candidate = out_root.joinpath(*parts).resolve()
        if candidate != resolved_target:
            continue
        digest = _product_checksum(target.read_bytes())
        if checksums.get(key) != digest:
            checksums[key] = digest
            changed = True
    if not changed:
        return

    text = json.dumps(product, ensure_ascii=False, indent="\t")
    next_bytes = text.encode("utf-8")
    if has_bom:
        next_bytes = b"\xef\xbb\xbf" + next_bytes
    _atomic_write(
        product_file,
        next_bytes,
        stat.S_IMODE(product_file.stat().st_mode),
    )


def _planned_extension_names(
    layout: CursorLayout,
    plan: Mapping[Path, PlannedFile],
) -> Set[str]:
    names: Set[str] = set()
    for file_path in plan:
        extension_name = _target_extension_name(layout, file_path)
        if extension_name:
            names.add(extension_name)
    return names


def _verify_extension_hashes(
    layout: CursorLayout,
    extension_names: Iterable[str],
) -> None:
    names = set(extension_names)
    if layout.ext_host_path is None or not names:
        return
    ext_content = _decode_js(layout.ext_host_path.read_bytes(), layout.ext_host_path)
    for rel, extension_name in TARGET_SPECS:
        if not extension_name or extension_name not in names:
            continue
        main_path = layout.app_root.joinpath(*rel.split("/"))
        if not main_path.is_file():
            continue
        extension_id = "anysphere." + extension_name
        if f'"{extension_id}"' not in ext_content:
            continue
        pattern = re.compile(
            rf"\"{re.escape(extension_id)}\"\s*:\s*\{{[\s\S]{{0,2400}}?"
            rf"\"main\.js\"\s*:\s*\"([0-9a-f]{{64}})\""
        )
        match = pattern.search(ext_content)
        if not match:
            continue
        expected = hashlib.sha256(main_path.read_bytes()).hexdigest()
        if match.group(1) != expected:
            raise SandToolError(f"{extension_id} 的内嵌哈希校验失败")


def _verify_product_checksums(layout: CursorLayout) -> int:
    product = json.loads(layout.product_json.read_bytes().decode("utf-8-sig"))
    checksums = product.get("checksums") if isinstance(product, dict) else None
    if not isinstance(checksums, dict):
        return 0
    out_root = (layout.app_root / "out").resolve()
    checked = 0
    for key, written in checksums.items():
        if not isinstance(key, str):
            continue
        parts = [part for part in re.split(r"[\\/]", key) if part]
        target = out_root.joinpath(*parts).resolve()
        if not _is_within(target, out_root) or not target.is_file():
            continue
        checked += 1
        if written != _product_checksum(target.read_bytes()):
            raise SandToolError(f"product.json 完整性哈希校验失败：{key}")
    return checked


def inspect_status(layout: CursorLayout) -> PatchStatus:
    client_markers = 0
    eligibility_markers = 0
    managed_local_route_markers = 0
    local_runtime_load_markers = 0
    session_stream_markers = 0
    direct_stream_markers = 0
    dsv3_local_loop_markers = 0
    agent_host_enablement_markers = 0
    agent_host_identity_markers = 0
    move_exec_markers = 0
    task_tool_markers = 0
    client_side_subagent_markers = 0
    subagent_turn_markers = 0
    ttft_markers = 0
    rules_skills_markers = 0
    rules_skills_legacy_markers = 0
    dsv3_legacy_markers = 0
    user_rules_markers = 0
    mcp_filesystem_markers = 0
    interaction_seq_markers = 0
    machine_id_markers = 0
    machine_mac_markers = 0
    machine_dev_markers = 0
    legacy_client_markers = 0
    legacy_eligibility_markers = 0
    ide_matches = 0
    external_sand_matches = 0
    external_marker_count = 0
    patched_files: List[Path] = []
    for target in layout.target_paths:
        content = _decode_js(target.read_bytes(), target)
        client_count = content.count(SAND_CLIENT_MARKER) + content.count(
            SAND_CLIENT_EXISTING_MARKER
        )
        eligibility_count = content.count(SAND_ELIGIBILITY_MARKER)
        managed_local_route_count = content.count(SAND_MANAGED_LOCAL_ROUTE_MARKER)
        local_runtime_load_count = content.count(SAND_LOCAL_RUNTIME_LOAD_MARKER)
        session_stream_count = content.count(SAND_SESSION_STREAM_MARKER)
        direct_stream_count = content.count(SAND_DIRECT_STREAM_MARKER)
        dsv3_local_loop_count = content.count(SAND_DSV3_DEGRADE_MARKER)
        dsv3_legacy_count = content.count(SAND_DSV3_LOCAL_LOOP_MARKER_V1)
        user_rules_count = content.count(SAND_USER_RULES_MARKER)
        mcp_filesystem_count = content.count(SAND_MCP_FILESYSTEM_MARKER)
        interaction_seq_count = content.count(SAND_INTERACTION_SEQ_MARKER)
        machine_id_count = content.count(SAND_MACHINE_ID_MARKER)
        machine_mac_count = content.count(SAND_MACHINE_MAC_MARKER)
        machine_dev_count = content.count(SAND_MACHINE_DEV_MARKER)
        agent_host_enablement_count = content.count(SAND_AGENT_HOST_ENABLEMENT_MARKER)
        agent_host_identity_count = content.count(SAND_AGENT_HOST_IDENTITY_MARKER)
        move_exec_count = content.count(SAND_MOVE_EXEC_MARKER)
        task_tool_count = content.count(SAND_TASK_TOOL_MARKER)
        client_side_subagent_count = content.count(SAND_CLIENT_SIDE_SUBAGENT_MARKER)
        subagent_turn_count = (
            content.count(SAND_SUBAGENT_TURN_MARKER)
            + content.count(SAND_SUBAGENT_FOLLOWUP_MARKER)
            + content.count(SAND_PLAN_BUILD_MARKER)
        )
        ttft_count = content.count(SAND_TTFT_MARKER)
        rules_skills_count = content.count(SAND_RULES_SKILLS_MARKER)
        rules_skills_legacy_count = (
            content.count(SAND_RULES_SKILLS_MARKER_V1)
            + content.count(SAND_RULES_SKILLS_MARKER_V2)
            + content.count(SAND_RULES_SKILLS_MARKER_V3)
        )
        legacy_client_count = len(
            re.findall(
                rf"([\"'])sand\1{LEGACY_CLIENT_MARKER_PATTERN}",
                content,
            )
        )
        legacy_eligibility_count = content.count(
            "return!1;" + LEGACY_SAND_ELIGIBILITY_MARKER
        )
        external_marker_count += max(
            0,
            len(re.findall(CLIENT_MARKER_GUARD_PATTERN, content))
            - client_count
            - legacy_client_count,
        )
        external_marker_count += max(
            0,
            len(re.findall(ELIGIBILITY_MARKER_GUARD_PATTERN, content))
            - eligibility_count
            - legacy_eligibility_count,
        )
        if (
            client_count
            + eligibility_count
            + legacy_client_count
            + legacy_eligibility_count
            + managed_local_route_count
            + local_runtime_load_count
            + session_stream_count
            + direct_stream_count
            + dsv3_local_loop_count
            + agent_host_enablement_count
            + agent_host_identity_count
            + move_exec_count
            + task_tool_count
            + client_side_subagent_count
            + subagent_turn_count
            + ttft_count
            + rules_skills_count
            + rules_skills_legacy_count
            + dsv3_legacy_count
            + user_rules_count
            + mcp_filesystem_count
            + interaction_seq_count
            + machine_id_count
            + machine_mac_count
            + machine_dev_count
        ):
            patched_files.append(target)
        client_markers += client_count
        eligibility_markers += eligibility_count
        legacy_client_markers += legacy_client_count
        legacy_eligibility_markers += legacy_eligibility_count
        managed_local_route_markers += managed_local_route_count
        local_runtime_load_markers += local_runtime_load_count
        session_stream_markers += session_stream_count
        direct_stream_markers += direct_stream_count
        dsv3_local_loop_markers += dsv3_local_loop_count
        dsv3_legacy_markers += dsv3_legacy_count
        user_rules_markers += user_rules_count
        mcp_filesystem_markers += mcp_filesystem_count
        interaction_seq_markers += interaction_seq_count
        machine_id_markers += machine_id_count
        machine_mac_markers += machine_mac_count
        machine_dev_markers += machine_dev_count
        agent_host_enablement_markers += agent_host_enablement_count
        agent_host_identity_markers += agent_host_identity_count
        move_exec_markers += move_exec_count
        task_tool_markers += task_tool_count
        client_side_subagent_markers += client_side_subagent_count
        subagent_turn_markers += subagent_turn_count
        ttft_markers += ttft_count
        rules_skills_markers += rules_skills_count
        rules_skills_legacy_markers += rules_skills_legacy_count
        for _key, rule in CLIENT_RULES:
            for match in rule.finditer(content):
                if match.group(3) == "sand":
                    external_sand_matches += 1
                else:
                    ide_matches += 1
    return PatchStatus(
        client_markers=client_markers,
        eligibility_markers=eligibility_markers,
        ide_matches=ide_matches,
        external_sand_matches=external_sand_matches,
        external_marker_count=external_marker_count,
        legacy_client_markers=legacy_client_markers,
        legacy_eligibility_markers=legacy_eligibility_markers,
        patched_files=tuple(patched_files),
        managed_local_route_markers=managed_local_route_markers,
        local_runtime_load_markers=local_runtime_load_markers,
        session_stream_markers=session_stream_markers,
        direct_stream_markers=direct_stream_markers,
        dsv3_local_loop_markers=dsv3_local_loop_markers,
        agent_host_enablement_markers=agent_host_enablement_markers,
        agent_host_identity_markers=agent_host_identity_markers,
        move_exec_markers=move_exec_markers,
        task_tool_markers=task_tool_markers,
        client_side_subagent_markers=client_side_subagent_markers,
        subagent_turn_markers=subagent_turn_markers,
        ttft_markers=ttft_markers,
        rules_skills_markers=rules_skills_markers,
        rules_skills_legacy_markers=rules_skills_legacy_markers,
        dsv3_legacy_markers=dsv3_legacy_markers,
        user_rules_markers=user_rules_markers,
        mcp_filesystem_markers=mcp_filesystem_markers,
        interaction_seq_markers=interaction_seq_markers,
        machine_id_markers=machine_id_markers,
        machine_mac_markers=machine_mac_markers,
        machine_dev_markers=machine_dev_markers,
    )


def _create_backup(
    layout: CursorLayout,
    plan: Mapping[Path, PlannedFile],
    operation: str,
) -> Tuple[Path, Dict[str, object]]:
    app_hash = hashlib.sha256(str(layout.app_root).encode("utf-8")).hexdigest()[:16]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = _config_dir() / "backups" / app_hash / f"{stamp}-{operation}"
    files_dir = backup_dir / "files"
    entries: List[Dict[str, object]] = []
    for path, planned in plan.items():
        try:
            relative = path.resolve().relative_to(layout.app_root.resolve())
        except ValueError as exc:
            raise SandToolError(f"计划文件逃逸出 Cursor app：{path}") from exc
        backup_file = files_dir / relative
        _atomic_write(backup_file, planned.original, planned.mode)
        entries.append(
            {
                "path": relative.as_posix(),
                "originalSha256": _sha256(planned.original),
                "nextSha256": _sha256(planned.next_bytes),
                "mode": planned.mode,
            }
        )
    manifest: Dict[str, object] = {
        "version": 1,
        "toolVersion": TOOL_VERSION,
        "operation": operation,
        "status": "prepared",
        "appRoot": str(layout.app_root),
        "cursorVersion": layout.version,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }
    _write_json_atomic(backup_dir / "manifest.json", manifest)
    return backup_dir, manifest


def _update_backup_manifest(
    backup_dir: Path,
    manifest: Dict[str, object],
    status_value: str,
    error: Optional[str] = None,
) -> None:
    manifest["status"] = status_value
    manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()
    if error:
        manifest["error"] = error[:1000]
    _write_json_atomic(backup_dir / "manifest.json", manifest)


def _commit_plan(
    layout: CursorLayout,
    plan: Mapping[Path, PlannedFile],
    operation: str,
    validator,
) -> Tuple[Tuple[Path, ...], Path]:
    if not plan:
        raise SandToolError("内部错误：提交计划为空")
    for path, planned in plan.items():
        if _sha256(path.read_bytes()) != _sha256(planned.original):
            raise SandToolError(f"文件在计划生成后发生变化，已停止操作：{path}")
    backup_dir, manifest = _create_backup(layout, plan, operation)
    attempted: List[Path] = []
    written: List[Path] = []
    try:
        for path, planned in plan.items():
            if _sha256(path.read_bytes()) != _sha256(planned.original):
                raise SandToolError(f"文件在写入前发生变化，已停止操作：{path}")
            attempted.append(path)
            _atomic_write(path, planned.next_bytes, planned.mode)
            written.append(path)
        validator()
        for path, planned in plan.items():
            if _sha256(path.read_bytes()) != _sha256(planned.next_bytes):
                raise SandToolError(f"写入后哈希校验失败：{path}")
        _update_backup_manifest(backup_dir, manifest, "committed")
        return tuple(written), backup_dir
    except (Exception, KeyboardInterrupt) as exc:
        rollback_errors: List[str] = []
        for path in reversed(attempted):
            planned = plan[path]
            try:
                current_hash = _sha256(path.read_bytes())
                original_hash = _sha256(planned.original)
                next_hash = _sha256(planned.next_bytes)
                if current_hash == original_hash:
                    continue
                if current_hash != next_hash:
                    rollback_errors.append(f"{path}: 文件已被外部修改，未覆盖")
                    continue
                _atomic_write(path, planned.original, planned.mode)
            except Exception as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")
        message = str(exc)
        if rollback_errors:
            message += "; rollback errors: " + " | ".join(rollback_errors)
        try:
            _update_backup_manifest(backup_dir, manifest, "rolled_back", message)
        except Exception:
            pass
        if rollback_errors:
            raise SandToolError(
                f"补丁失败且有文件未能自动回滚，请保留备份目录：{backup_dir}\n{message}"
            ) from exc
        raise


def _windows_close_cursor(layout: CursorLayout) -> int:
    powershell = _powershell_executable()
    if not powershell:
        raise SandToolError("未找到 PowerShell，无法安全关闭 Cursor")
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$target = [System.IO.Path]::GetFullPath($env:SAND_CURSOR_EXE)
function Get-SandCursorTargets {
  @(Get-CimInstance Win32_Process -Filter "Name='Cursor.exe'" -ErrorAction Stop | Where-Object {
    $_.ExecutablePath -and [string]::Equals(
      [System.IO.Path]::GetFullPath($_.ExecutablePath),
      $target,
      [System.StringComparison]::OrdinalIgnoreCase
    )
  })
}
$before = @(Get-SandCursorTargets)
foreach ($item in $before) {
  try {
    $process = Get-Process -Id $item.ProcessId -ErrorAction Stop
    if ($process.MainWindowHandle -ne 0) { [void]$process.CloseMainWindow() }
  } catch {}
}
$deadline = [DateTime]::UtcNow.AddSeconds(12)
while ([DateTime]::UtcNow -lt $deadline -and @(Get-SandCursorTargets).Count -gt 0) {
  Start-Sleep -Milliseconds 250
}
$remaining = @(Get-SandCursorTargets)
foreach ($item in $remaining) {
  try { Stop-Process -Id $item.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Milliseconds 500
if (@(Get-SandCursorTargets).Count -gt 0) { exit 3 }
Write-Output ("CLOSED=" + $before.Count)
""".strip()
    env = dict(os.environ)
    env["SAND_CURSOR_EXE"] = str(layout.executable)
    try:
        result = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandToolError("无法安全关闭所选 Cursor 进程，请手动退出后重试") from exc
    if result.returncode != 0:
        raise SandToolError("无法安全关闭所选 Cursor 进程，请手动退出后重试")
    match = re.search(r"CLOSED=(\d+)", result.stdout)
    return int(match.group(1)) if match else 0


def _mac_bundle_pids(layout: CursorLayout) -> List[int]:
    bundle = _find_app_bundle(layout.app_root)
    if bundle is None:
        return []
    contents = (bundle.resolve() / "Contents").resolve()
    pids: List[int] = []
    for pid, executable in _mac_process_paths(strict=True):
        if pid != os.getpid() and _is_within(executable, contents):
            pids.append(pid)
    return pids


def _wait_for_mac_exit(layout: CursorLayout, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _mac_bundle_pids(layout):
            return True
        time.sleep(0.25)
    return not _mac_bundle_pids(layout)


def _mac_close_cursor(layout: CursorLayout) -> int:
    before = _mac_bundle_pids(layout)
    if not before:
        return 0
    selected_bundle = _find_app_bundle(layout.app_root)
    running_bundles: Dict[str, Path] = {}
    for _pid, executable in _mac_process_paths(strict=True):
        bundle = _bundle_for_executable(executable)
        if bundle is not None:
            running_bundles.setdefault(_path_key(bundle), bundle)
    if selected_bundle is not None and len(running_bundles) == 1:
        osascript = shutil.which("osascript") or "/usr/bin/osascript"
        try:
            subprocess.run(
                [
                    osascript,
                    "-e",
                    'tell application id "com.todesktop.230313mzl4w4u92" to quit',
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if _wait_for_mac_exit(layout, 12):
            return len(before)

    for pid in _mac_bundle_pids(layout):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    if _wait_for_mac_exit(layout, 3):
        return len(before)

    for pid in _mac_bundle_pids(layout):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    if not _wait_for_mac_exit(layout, 2):
        raise SandToolError("无法安全关闭所选 Cursor 进程，请手动退出后重试")
    return len(before)


def close_cursor(layout: CursorLayout) -> int:
    if sys.platform == "win32":
        return _windows_close_cursor(layout)
    if sys.platform == "darwin":
        return _mac_close_cursor(layout)
    raise SandToolError("当前仅支持 Windows 和 macOS")


def start_cursor(layout: CursorLayout) -> bool:
    try:
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(
                [str(layout.executable)],
                cwd=str(layout.install_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=0x00000008 | 0x00000200,
            )
            return True
        if sys.platform == "darwin":
            bundle = _find_app_bundle(layout.app_root)
            if bundle is None:
                return False
            subprocess.run(
                [shutil.which("open") or "/usr/bin/open", "-a", str(bundle)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
            return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def _move_exec_main_js(layout: CursorLayout) -> Path:
    return layout.app_root / "extensions" / "cursor-agent-host" / "dist" / "main.js"


def move_exec_state(layout: CursorLayout) -> Tuple[bool, bool]:
    path = _move_exec_main_js(layout)
    if not path.is_file():
        return False, False
    content = _decode_js(path.read_bytes(), path)
    return (SAND_MOVE_EXEC_MARKER in content, MOVE_EXEC_ORIGINAL in content)


def cmd_move_exec_check(layout: CursorLayout) -> int:
    patched, original = move_exec_state(layout)
    print(f"[move-exec] 文件: {_move_exec_main_js(layout)}")
    if patched:
        print("[move-exec] 结论: 已强制 move_exec ON（已补丁）")
    elif original:
        print("[move-exec] 结论: 仍走 move_exec gate（未补丁，工具会崩）")
    else:
        print("[move-exec] 结论: 未匹配到目标代码（版本不同？）")
    return 0


def cmd_move_exec_apply(layout: CursorLayout) -> int:
    patched, original = move_exec_state(layout)
    if patched:
        print("[move-exec] 已补丁，跳过")
        return 0
    if not original:
        print("[move-exec] 错误: 未找到目标代码，无法补丁（版本不同？）")
        return 1
    path = _move_exec_main_js(layout)
    backup_dir = _config_dir() / "move_exec_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / "main.js"
    if not backup_file.exists():
        backup_file.write_bytes(path.read_bytes())
        print(f"[move-exec] 已备份到 {backup_file}")
    close_cursor(layout)
    content = _decode_js(path.read_bytes(), path)
    content = content.replace(MOVE_EXEC_ORIGINAL, MOVE_EXEC_PATCHED, 1)
    _atomic_write(path, content.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    print("[move-exec] 补丁完成: move_exec 已强制 ON")
    start_cursor(layout)
    return 0


def cmd_move_exec_restore(layout: CursorLayout) -> int:
    patched, original = move_exec_state(layout)
    if not patched:
        print("[move-exec] 未打补丁，跳过")
        return 0
    path = _move_exec_main_js(layout)
    backup_file = _config_dir() / "move_exec_backup" / "main.js"
    if backup_file.exists():
        close_cursor(layout)
        _atomic_write(path, backup_file.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        print("[move-exec] 已从备份还原")
        start_cursor(layout)
        return 0
    if MOVE_EXEC_PATCHED in _decode_js(path.read_bytes(), path):
        close_cursor(layout)
        content = _decode_js(path.read_bytes(), path)
        content = content.replace(MOVE_EXEC_PATCHED, MOVE_EXEC_ORIGINAL, 1)
        _atomic_write(path, content.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
        print("[move-exec] 已反向替换还原")
        start_cursor(layout)
        return 0
    print("[move-exec] 错误: 既无备份又找不到补丁串，无法还原")
    return 1


def _ttft_workbench_js(layout: CursorLayout) -> Path:
    return layout.app_root / "out" / "vs" / "workbench" / "workbench.desktop.main.js"


def ttft_state(layout: CursorLayout) -> Tuple[bool, bool, int]:
    path = _ttft_workbench_js(layout)
    if not path.is_file():
        return False, False, 0
    content = _decode_js(path.read_bytes(), path)
    return (
        SAND_TTFT_MARKER in content,
        any(original in content for original in TTFT_ORIGINALS),
        sum(content.count(original) for original in TTFT_ORIGINALS),
    )


def _ttft_checksum_record(layout: CursorLayout) -> Optional[str]:
    """返回 product.json 里 workbench.desktop.main.js 对应的记录值；不存在返回 None。"""
    try:
        product = json.loads(layout.product_json.read_bytes().decode("utf-8-sig"))
    except Exception:
        return None
    checksums = product.get("checksums") if isinstance(product, dict) else None
    if not isinstance(checksums, dict):
        return None
    out_root = (layout.app_root / "out").resolve()
    resolved_target = _ttft_workbench_js(layout).resolve()
    for key, value in checksums.items():
        if not isinstance(key, str):
            continue
        parts = [part for part in re.split(r"[\\/]", key) if part]
        candidate = out_root.joinpath(*parts).resolve()
        if candidate == resolved_target:
            return str(value)
    return None


def ttft_checksum_ok(layout: CursorLayout) -> bool:
    """product.json 的 checksum 是否与磁盘上的 workbench.desktop.main.js 一致。"""
    path = _ttft_workbench_js(layout)
    if not path.is_file():
        return True
    recorded = _ttft_checksum_record(layout)
    if recorded is None:
        return True
    actual = _product_checksum(path.read_bytes())
    return recorded == actual


def cmd_ttft_check(layout: CursorLayout) -> int:
    patched, original, count = ttft_state(layout)
    print(f"[ttft] 文件: {_ttft_workbench_js(layout)}")
    if patched:
        print("[ttft] 结论: 首字超时已 1s（已补丁）")
    elif original:
        print(f"[ttft] 结论: 首字超时仍 10s（未补丁，命中 {count} 处）")
    else:
        print("[ttft] 结论: 未匹配到目标代码（版本不同？）")
    if not ttft_checksum_ok(layout):
        print(
            "[ttft] 警告: product.json 校验和与文件不一致，"
            "Cursor 可能报安装损坏；请运行 ttft-sync 修复"
        )
    return 0


def cmd_ttft_sync(layout: CursorLayout) -> int:
    """幂等同步 product.json 的 checksum 为磁盘当前值，修复 corrupt。"""
    path = _ttft_workbench_js(layout)
    if not path.is_file():
        print("[ttft] 目标文件不存在，跳过")
        return 1
    if ttft_checksum_ok(layout):
        print("[ttft] 校验和已一致，无需同步")
        return 0
    recorded = _ttft_checksum_record(layout)
    actual = _product_checksum(path.read_bytes())
    _sync_checksum_for_target(layout, path)
    print(f"[ttft] 已同步校验和: {recorded} -> {actual}")
    return 0


def cmd_ttft_apply(layout: CursorLayout) -> int:
    patched, original, count = ttft_state(layout)
    if patched:
        print("[ttft] 已补丁，跳过")
        return 0
    if not original:
        print("[ttft] 错误: 未找到目标代码，无法补丁（版本不同？）")
        return 1
    if count != 1:
        print(
            f"[ttft] 错误: 目标代码出现 {count} 处，不唯一，拒绝补丁"
            "（版本改版？请重新确认锚点）"
        )
        return 1
    path = _ttft_workbench_js(layout)
    close_cursor(layout)
    content = _decode_js(path.read_bytes(), path)
    matched = next(o for o in TTFT_ORIGINALS if o in content)
    patched_text = matched.replace("=1e4", "=1e3") + SAND_TTFT_MARKER
    content = content.replace(matched, patched_text, 1)
    _atomic_write(path, content.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    _sync_checksum_for_target(layout, path)
    print(f"[ttft] 补丁完成: 首字超时已从 10s 改为 1s（锚点 {matched}）")
    start_cursor(layout)
    return 0


def cmd_ttft_restore(layout: CursorLayout) -> int:
    patched, _original, _count = ttft_state(layout)
    if not patched:
        print("[ttft] 未打补丁，跳过")
        return 0
    path = _ttft_workbench_js(layout)
    content = _decode_js(path.read_bytes(), path)
    if not TTFT_RESTORE_RE.search(content):
        print("[ttft] 错误: 找不到补丁串，拒绝还原（避免整文件覆盖其它补丁）")
        return 1
    close_cursor(layout)
    content = TTFT_RESTORE_RE.sub(lambda m: m.group(1) + "=1e4", content, count=1)
    _atomic_write(path, content.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    _sync_checksum_for_target(layout, path)
    print("[ttft] 已反向替换还原")
    start_cursor(layout)
    return 0


def _rules_skills_exec_js(layout: CursorLayout) -> Path:
    return layout.app_root / "extensions" / "cursor-agent-exec" / "dist" / "main.js"


def rules_skills_state(layout: CursorLayout) -> Tuple[bool, bool, int, int]:
    """返回 (已打 V4, 存在 aa() 锚点, 锚点次数, 旧版 V1–V3 标记数)。"""
    path = _rules_skills_exec_js(layout)
    host = layout.app_root / "extensions" / "cursor-agent-host" / "dist" / "main.js"
    exec_content = _decode_js(path.read_bytes(), path) if path.is_file() else ""
    host_content = _decode_js(host.read_bytes(), host) if host.is_file() else ""
    legacy = (
        exec_content.count(SAND_RULES_SKILLS_MARKER_V1)
        + exec_content.count(SAND_RULES_SKILLS_MARKER_V2)
        + exec_content.count(SAND_RULES_SKILLS_MARKER_V3)
        + host_content.count(SAND_RULES_SKILLS_MARKER_V1)
        + host_content.count(SAND_RULES_SKILLS_MARKER_V2)
        + host_content.count(SAND_RULES_SKILLS_MARKER_V3)
    )
    if not path.is_file():
        return False, False, 0, legacy
    return (
        SAND_RULES_SKILLS_MARKER in exec_content,
        RULES_SKILLS_EXEC_ORIGINAL in exec_content,
        exec_content.count(RULES_SKILLS_EXEC_ORIGINAL),
        legacy,
    )


def cmd_rules_skills_check(layout: CursorLayout) -> int:
    patched, original, count, legacy = rules_skills_state(layout)
    print(f"[rules-skills] 文件: {_rules_skills_exec_js(layout)}")
    if patched:
        print("[rules-skills] 结论: 已补调 agent-exec aa()→na()（V4）")
    elif legacy:
        print("[rules-skills] 结论: 检测到旧版 V1–V3 残留，请重新 install")
        return 1
    elif original and count == 1:
        print("[rules-skills] 结论: 未补丁（host 启用时 rules/skills 不会推送）")
    elif original:
        print(f"[rules-skills] 结论: 锚点出现 {count} 处，不唯一（版本改版？）")
        return 1
    else:
        print("[rules-skills] 结论: 未匹配到目标代码（版本不同？）")
        return 1
    return 0


def _cursor_main_js(layout: CursorLayout) -> Path:
    return layout.app_root / "out" / "main.js"


def cmd_machine_id_check(layout: CursorLayout) -> int:
    path = _cursor_main_js(layout)
    content = _decode_js(path.read_bytes(), path) if path.is_file() else ""
    k6 = content.count(SAND_MACHINE_ID_MARKER)
    mac = content.count(SAND_MACHINE_MAC_MARKER)
    dev = content.count(SAND_MACHINE_DEV_MARKER)
    ident = _identity_from_dict(_try_load_config().get("spoofedIdentity"))
    storage = storage_matches_identity(ident) if ident is not None else None
    print(f"[machine-id] 文件: {path}")
    if k6 == 1 and mac == 1 and dev == 1:
        print("[machine-id] 采集函数: 已伪装（K6 + B9e + z6）")
    elif k6 or mac or dev:
        print(
            f"[machine-id] 采集函数: 不完整（K6={k6}, B9e={mac}, z6={dev}），请重新 install"
        )
        return 1
    elif (
        MACHINE_ID_K6_ORIGINAL in content
        and MACHINE_MAC_B9E_ORIGINAL in content
        and MACHINE_DEV_Z6_ORIGINAL in content
    ):
        print("[machine-id] 采集函数: 未伪装，仍读真实硬件")
        return 1
    else:
        print("[machine-id] 采集函数: 未匹配到锚点（版本不同？）")
        return 1
    if ident is None:
        print("[machine-id] 假身份: 配置里没有，请重新 install")
        return 1
    if storage is None:
        print("[machine-id] storage.json: 不存在（下次启动会按伪装值写入）")
    elif storage:
        print("[machine-id] storage.json: 已与伪装身份同步")
    else:
        print("[machine-id] storage.json: 未同步，请重新 install")
        return 1
    return 0


def cmd_machine_id_restore(layout: CursorLayout) -> int:
    path = _cursor_main_js(layout)
    if not path.is_file():
        print("[machine-id] 错误: 找不到 out/main.js")
        return 1
    content = _decode_js(path.read_bytes(), path)
    if (
        SAND_MACHINE_ID_MARKER not in content
        and SAND_MACHINE_MAC_MARKER not in content
        and SAND_MACHINE_DEV_MARKER not in content
    ):
        print("[machine-id] 未打伪装补丁，跳过")
        return 0
    close_cursor(layout)
    next_content, restored = remove_machine_id_from_content(content)
    expected = sum(
        1
        for marker in (
            SAND_MACHINE_ID_MARKER,
            SAND_MACHINE_MAC_MARKER,
            SAND_MACHINE_DEV_MARKER,
        )
        if marker in content
    )
    if restored != expected:
        print(
            f"[machine-id] 错误: 还原数量异常（{restored}/{expected}），拒绝写入"
        )
        return 1
    _atomic_write(path, next_content.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    _sync_checksum_for_target(layout, path)
    print("[machine-id] 已还原采集函数。下次启动会重新读取并上传真实机器码")
    start_cursor(layout)
    return 0


def _build_install_plan(
    layout: CursorLayout,
    transport: str = STREAM_TRANSPORT_SESSION,
) -> Tuple[Dict[Path, PlannedFile], PatchStats]:
    plan: Dict[Path, PlannedFile] = {}
    total = PatchStats()
    transport = _validate_stream_transport(transport)
    identity = _load_or_create_spoofed_identity()
    for target in layout.target_paths:
        original = _read_planned_file(target)
        content = _decode_js(original.original, target)
        next_content, stats = apply_patch_to_content(content, transport, identity)
        if next_content != content:
            plan[target] = PlannedFile(
                original=original.original,
                next_bytes=next_content.encode("utf-8"),
                mode=original.mode,
            )
        total.is_glass += stats.is_glass
        total.object_header += stats.object_header
        total.set_header += stats.set_header
        total.eligibility += stats.eligibility
        total.adopted_sand += stats.adopted_sand
        total.migrated_client += stats.migrated_client
        total.migrated_eligibility += stats.migrated_eligibility
        total.managed_local_route += stats.managed_local_route
        total.local_runtime_load += stats.local_runtime_load
        total.session_stream += stats.session_stream
        total.direct_stream += stats.direct_stream
        total.dsv3_local_loop += stats.dsv3_local_loop
        total.agent_host_enablement += stats.agent_host_enablement
        total.agent_host_identity += stats.agent_host_identity
        total.move_exec += stats.move_exec
        total.task_tool += stats.task_tool
        total.client_side_subagent += stats.client_side_subagent
        total.subagent_turn += stats.subagent_turn
        total.ttft += stats.ttft
        total.rules_skills += stats.rules_skills
        total.user_rules += stats.user_rules
        total.mcp_filesystem += stats.mcp_filesystem
        total.interaction_seq += stats.interaction_seq
        total.machine_id += stats.machine_id
        total.machine_mac += stats.machine_mac
        total.machine_dev += stats.machine_dev
    if plan:
        _update_extension_hashes(layout, plan)
        _sync_product_checksums(layout, plan)
    return plan, total


def _build_uninstall_plan(
    layout: CursorLayout,
) -> Tuple[Dict[Path, PlannedFile], RemoveStats]:
    plan: Dict[Path, PlannedFile] = {}
    total = RemoveStats()
    for target in layout.target_paths:
        original = _read_planned_file(target)
        content = _decode_js(original.original, target)
        next_content, stats = remove_patch_from_content(content)
        if next_content != content:
            plan[target] = PlannedFile(
                original=original.original,
                next_bytes=next_content.encode("utf-8"),
                mode=original.mode,
            )
        total.client_type += stats.client_type
        total.eligibility += stats.eligibility
        total.managed_local_route += stats.managed_local_route
        total.local_runtime_load += stats.local_runtime_load
        total.session_stream += stats.session_stream
        total.direct_stream += stats.direct_stream
        total.dsv3_local_loop += stats.dsv3_local_loop
        total.agent_host_enablement += stats.agent_host_enablement
        total.agent_host_identity += stats.agent_host_identity
        total.move_exec += stats.move_exec
        total.task_tool += stats.task_tool
        total.client_side_subagent += stats.client_side_subagent
        total.subagent_turn += stats.subagent_turn
        total.ttft += stats.ttft
        total.rules_skills += stats.rules_skills
        total.user_rules += stats.user_rules
        total.mcp_filesystem += stats.mcp_filesystem
        total.interaction_seq += stats.interaction_seq
    if plan:
        _update_extension_hashes(layout, plan)
        _sync_product_checksums(layout, plan)
    return plan, total


def install(
    layout: CursorLayout,
    transport: str = STREAM_TRANSPORT_SESSION,
) -> int:
    if layout.version != SUPPORTED_CURSOR_VERSION:
        raise SandToolError(
            f"当前 Cursor 版本为 {layout.version}，"
            f"本工具仅适配 Cursor {SUPPORTED_CURSOR_VERSION}。"
            "请更换为适配版本后再安装"
        )
    before = inspect_status(layout)
    if before.external_marker_count:
        raise SandToolError(
            "检测到其他 Sand 模式标记，本脚本不会接管或覆盖它；请先用原安装方式卸载"
        )
    transport = _validate_stream_transport(transport)
    plan, _stats = _build_install_plan(layout, transport)
    if not plan:
        if (
            before.installed
            and before.stream_mode_installed
            and before.stream_transport == transport
            and before.machine_id_spoofed
        ):
            close_cursor(layout)
            apply_spoofed_storage(_load_or_create_spoofed_identity())
            start_cursor(layout)
            return 0
        raise SandToolError("当前 Cursor 版本未匹配到 Sand 客户端模式规则")
    expect_session = 1 if transport == STREAM_TRANSPORT_SESSION else 0
    expect_direct = 1 if transport == STREAM_TRANSPORT_DIRECT else 0
    session_after = (
        before.session_stream_markers + _stats.session_stream
        if transport == STREAM_TRANSPORT_SESSION
        else 0
    )
    direct_after = (
        before.direct_stream_markers + _stats.direct_stream
        if transport == STREAM_TRANSPORT_DIRECT
        else 0
    )
    if (
        before.managed_local_route_markers + _stats.managed_local_route != 1
        or (before.local_runtime_load_markers + _stats.local_runtime_load != 1)
        or (before.agent_host_identity_markers + _stats.agent_host_identity != 1)
        or session_after != expect_session
        or direct_after != expect_direct
        or before.dsv3_local_loop_markers + _stats.dsv3_local_loop != 1
        or (before.agent_host_enablement_markers + _stats.agent_host_enablement != 2)
        or before.ttft_markers + _stats.ttft != 1
        or before.rules_skills_markers + _stats.rules_skills != 1
        or before.user_rules_markers + _stats.user_rules != 1
        or before.mcp_filesystem_markers + _stats.mcp_filesystem != 1
        or before.interaction_seq_markers + _stats.interaction_seq != 1
        or before.machine_id_markers + _stats.machine_id != 1
        or before.machine_mac_markers + _stats.machine_mac != 1
        or before.machine_dev_markers + _stats.machine_dev != 1
    ):
        raise SandToolError(
            "当前 Cursor 版本未完整匹配 Sand Stream 规则："
            f"route={before.managed_local_route_markers + _stats.managed_local_route}, "
            "runtimeLoad="
            f"{before.local_runtime_load_markers + _stats.local_runtime_load}, "
            "identity="
            f"{before.agent_host_identity_markers + _stats.agent_host_identity}, "
            f"sessionStream={before.session_stream_markers + _stats.session_stream}, "
            f"directStream={before.direct_stream_markers + _stats.direct_stream}, "
            f"dsv3={before.dsv3_local_loop_markers + _stats.dsv3_local_loop}, "
            "agentHost="
            f"{before.agent_host_enablement_markers + _stats.agent_host_enablement}, "
            f"ttft={before.ttft_markers + _stats.ttft}, "
            f"rulesSkills={before.rules_skills_markers + _stats.rules_skills}, "
            f"userRules={before.user_rules_markers + _stats.user_rules}, "
            f"mcpFs={before.mcp_filesystem_markers + _stats.mcp_filesystem}, "
            f"interactionSeq={before.interaction_seq_markers + _stats.interaction_seq}, "
            f"machineId={before.machine_id_markers + _stats.machine_id}, "
            f"machineMac={before.machine_mac_markers + _stats.machine_mac}, "
            f"machineDev={before.machine_dev_markers + _stats.machine_dev}"
        )

    close_cursor(layout)
    changed_extensions = _planned_extension_names(layout, plan)

    def validate() -> None:
        status = inspect_status(layout)
        if (
            not status.installed
            or not status.stream_mode_installed
            or status.stream_transport != transport
            or status.ide_matches != 0
            or status.external_marker_count != 0
            or status.legacy_client_markers != 0
            or status.legacy_eligibility_markers != 0
            or status.dsv3_local_loop_markers != 1
            or status.dsv3_legacy_markers != 0
            or status.ttft_markers != 1
            or status.rules_skills_markers != 1
            or status.rules_skills_legacy_markers != 0
            or status.user_rules_markers != 1
            or status.mcp_filesystem_markers != 1
            or status.interaction_seq_markers != 1
            or status.machine_id_markers != 1
            or status.machine_mac_markers != 1
            or status.machine_dev_markers != 1
        ):
            raise SandToolError(
                "安装后状态校验失败："
                f"markers={status.client_markers + status.eligibility_markers}, "
                f"remainingIde={status.ide_matches}, "
                f"streamMode={status.stream_mode_installed}, "
                f"transport={status.stream_transport}, "
                f"dsv3={status.dsv3_local_loop_markers}, "
                f"dsv3Legacy={status.dsv3_legacy_markers}, "
                "remainingLegacy="
                f"{status.legacy_client_markers + status.legacy_eligibility_markers}, "
                f"ttft={status.ttft_markers}, "
                f"rulesSkills={status.rules_skills_markers}, "
                f"rulesSkillsLegacy={status.rules_skills_legacy_markers}, "
                f"userRules={status.user_rules_markers}, "
                f"mcpFs={status.mcp_filesystem_markers}, "
                f"interactionSeq={status.interaction_seq_markers}, "
                f"machineId={status.machine_id_markers}, "
                f"machineMac={status.machine_mac_markers}, "
                f"machineDev={status.machine_dev_markers}"
            )
        _verify_extension_hashes(layout, changed_extensions)
        _verify_product_checksums(layout)

    _commit_plan(layout, plan, "install", validate)
    apply_spoofed_storage(_load_or_create_spoofed_identity())
    close_cursor(layout)
    start_cursor(layout)
    return 0


def uninstall(layout: CursorLayout) -> int:
    before = inspect_status(layout)
    if before.external_marker_count:
        raise SandToolError(
            "检测到无法识别的 Sand 模式标记，拒绝修改；请先用原安装方式卸载"
        )
    plan, _stats = _build_uninstall_plan(layout)
    if not plan:
        start_cursor(layout)
        return 0

    close_cursor(layout)
    changed_extensions = _planned_extension_names(layout, plan)

    def validate() -> None:
        status = inspect_status(layout)
        if status.installed or status.external_marker_count:
            raise SandToolError(
                "卸载后仍有 Sand marker："
                f"{status.client_markers + status.eligibility_markers}，"
                f"external={status.external_marker_count}"
            )
        _verify_extension_hashes(layout, changed_extensions)
        _verify_product_checksums(layout)

    _commit_plan(layout, plan, "uninstall", validate)
    close_cursor(layout)
    start_cursor(layout)
    return 0


def _permission_hint() -> str:
    script = Path(__file__).resolve()
    if sys.platform == "win32":
        return "请右键以管理员身份打开 PowerShell/终端后重新运行命令。"
    return f'请使用管理员权限重试：sudo python3 "{script}" <命令>'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{TOOL_NAME} - Cursor 客户端模式管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python sand_stream_installer.py install\n"
            "  python sand_stream_installer.py install --transport direct\n"
            "  python sand_stream_installer.py uninstall\n"
            '  python sand_stream_installer.py set-path "E:\\Development\\IDE\\cursor"\n'
            "  python3 sand_stream_installer.py set-path /Applications/Cursor.app\n"
            "  python sand_stream_installer.py set-path auto"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {TOOL_VERSION}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install", help="安装/注入 Sand 客户端模式")
    install_parser.add_argument(
        "--transport",
        choices=STREAM_TRANSPORTS,
        default=STREAM_TRANSPORT_SESSION,
        help="推理传输：session 复用原生会话流（默认，网页 Usage 走 bot）；direct 旧版直连回退",
    )
    commands.add_parser("uninstall", help="卸载 Sand 客户端模式")
    commands.add_parser("move-exec-check", help="检查 move_exec 补丁状态")
    commands.add_parser("move-exec-apply", help="单独应用 move_exec 补丁")
    commands.add_parser("move-exec-restore", help="单独还原 move_exec 补丁")
    commands.add_parser("ttft-check", help="检查首字(TTFT)超时补丁状态")
    commands.add_parser("ttft-apply", help="应用首字(TTFT)超时优化（10s → 1s）")
    commands.add_parser("ttft-restore", help="还原首字(TTFT)超时优化")
    commands.add_parser("ttft-sync", help="同步 product.json 校验和（修复 corrupt）")
    commands.add_parser("rules-skills-check", help="检查 Rules/Skills 恢复补丁状态")
    commands.add_parser("machine-id-check", help="检查机器码伪装状态")
    commands.add_parser(
        "machine-id-restore",
        help="还原机器码采集（会重新暴露真实硬件标识，默认不要用）",
    )
    set_path = commands.add_parser(
        "set-path", help="设置 Cursor 路径；auto 恢复自动检测"
    )
    set_path.add_argument(
        "path",
        help="Cursor.exe、Cursor.app、resources/app、安装根目录，或 auto",
    )
    return parser


def collect_status_lines() -> List[Tuple[str, str]]:
    try:
        layout = resolve_cursor_layout()
        status = inspect_status(layout)
    except SandToolError as exc:
        return [(str(exc), ANSI_YELLOW)]

    lines: List[Tuple[str, str]] = [
        (f"[环境] Cursor {layout.version}  |  {layout.install_root}", ANSI_BLUE),
        (f"[适配] 仅支持 Cursor {SUPPORTED_CURSOR_VERSION}", ANSI_GREEN),
    ]
    if layout.version != SUPPORTED_CURSOR_VERSION:
        lines.append(
            (
                f"[警告] 当前版本 {layout.version} 不受支持，请勿安装",
                ANSI_RED,
            )
        )
    if status.installed:
        if status.stream_mode_installed:
            label = _stream_transport_label(status.stream_transport)
            lines.append((f"[状态] Stream 模式已启用（{label}）", ANSI_GREEN))
        else:
            lines.append(("[状态] 检测到旧版客户端模式", ANSI_YELLOW))
    else:
        lines.append(("[状态] Cursor 原版模式", ANSI_YELLOW))
    if status.move_exec_markers:
        lines.append(("[move-exec] 工具执行补丁已启用", ANSI_GREEN))
    elif status.installed:
        lines.append(("[move-exec] 工具执行补丁未启用", ANSI_YELLOW))
    ttft_patched, ttft_original, _ttft_count = ttft_state(layout)
    if ttft_patched:
        lines.append(("[ttft] 首字超时已 1s（已补丁）", ANSI_GREEN))
    elif ttft_original:
        lines.append(("[ttft] 首字超时仍 10s（未补丁）", ANSI_YELLOW))
    if not ttft_checksum_ok(layout):
        lines.append(("[ttft] 校验和失配，请运行 ttft-sync 修复", ANSI_RED))
    if status.rules_skills_markers:
        lines.append(("[rules-skills] Rules/Skills 恢复已启用", ANSI_GREEN))
    elif status.rules_skills_legacy_markers:
        lines.append(("[rules-skills] 旧版补丁残留，请重新 install", ANSI_RED))
    elif status.installed:
        lines.append(("[rules-skills] Rules/Skills 恢复未启用", ANSI_YELLOW))
    if status.user_rules_markers:
        lines.append(("[user-rules] Settings User Rules 注入已启用", ANSI_GREEN))
    elif status.installed:
        lines.append(
            ("[user-rules] Settings User Rules 注入未启用，请重新 install", ANSI_YELLOW)
        )
    if status.mcp_filesystem_markers:
        lines.append(("[mcp] MCP FileSystem 提示块已启用", ANSI_GREEN))
    elif status.installed:
        lines.append(("[mcp] MCP 提示块未启用，请重新 install", ANSI_YELLOW))
    if status.interaction_seq_markers:
        lines.append(
            ("[plan-fix] 同 turn 多次交互（问答→建计划）串号修复已启用", ANSI_GREEN)
        )
    elif status.installed:
        lines.append(("[plan-fix] 交互串号修复未启用，请重新 install", ANSI_YELLOW))
    if status.machine_id_spoofed:
        lines.append(("[machine-id] 机器码已伪装（uninstall 不会还原）", ANSI_GREEN))
    elif status.machine_id_markers or status.machine_mac_markers or status.machine_dev_markers:
        lines.append(("[machine-id] 机器码伪装不完整，请重新 install", ANSI_RED))
    elif status.installed:
        lines.append(("[machine-id] 机器码未伪装，请重新 install", ANSI_YELLOW))
    if status.dsv3_legacy_markers:
        lines.append(("[dsv3] 旧版 V1 守卫补丁残留，请重新 install", ANSI_RED))
    elif status.dsv3_local_loop_markers:
        lines.append(
            ("[dsv3] Composer/Auto/grok-4.6 已降级到通用 harness（V2）", ANSI_GREEN)
        )
    elif status.installed:
        lines.append(("[dsv3] DSV3 模型降级未启用，请重新 install", ANSI_YELLOW))
    if (
        status.task_tool_markers
        and status.client_side_subagent_markers
        and status.subagent_turn_markers
    ):
        lines.append(("[subagent] 子 agent（Task）已启用", ANSI_GREEN))
    elif status.installed:
        lines.append(("[subagent] 子 agent（Task）未启用", ANSI_YELLOW))
    if status.external_marker_count:
        lines.append(
            (
                f"[注意] 检测到其他工具标记：{status.external_marker_count} 处",
                ANSI_YELLOW,
            )
        )
    return lines


def print_banner() -> None:
    width = 60
    print(colorize("=" * width, ANSI_BLUE))
    print(colorize(f"  {TOOL_NAME}  v{TOOL_VERSION}", ANSI_BOLD, ANSI_GREEN))
    print(colorize("  Cursor 客户端模式管理器", ANSI_BOLD))
    print(colorize("=" * width, ANSI_BLUE))
    for text, code in collect_status_lines():
        print(colorize(text, code))
    print()


def apply_set_path(value: str) -> int:
    save_cursor_path(value)
    return 0


def print_menu() -> None:
    print(colorize("请选择操作：", ANSI_BOLD))
    print(colorize("  [1]", ANSI_BOLD, ANSI_GREEN) + " 启用 Stream 模式")
    print(colorize("  [2]", ANSI_BOLD, ANSI_GREEN) + " 恢复 Cursor 原版")
    print(colorize("  [3]", ANSI_BOLD, ANSI_GREEN) + " 指定 Cursor 路径")
    print(colorize("  [0]", ANSI_BOLD, ANSI_BLUE) + " 退出")


def prompt_set_path() -> int:
    value = input(colorize("路径> ", ANSI_BLUE)).strip()
    if not value:
        return 0
    with LoadingSpinner("正在设置路径"):
        result = apply_set_path(value)
    print_success("✓ Cursor 路径已保存")
    return result


def run_choice(choice: str) -> Optional[int]:
    if choice == "1":
        with LoadingSpinner("正在启用 Stream 模式"):
            result = install(resolve_cursor_layout())
        print_success("✓ Stream 模式已启用（会话流），Cursor 已重新启动")
        return result
    if choice == "2":
        with LoadingSpinner("正在恢复 Cursor 原版"):
            result = uninstall(resolve_cursor_layout())
        print_success("✓ 已恢复 Cursor 原版，Cursor 已重新启动")
        return result
    if choice == "3":
        return prompt_set_path()
    print_warn("无效选项，请输入 0-3。")
    return 0


def interactive_loop() -> int:
    while True:
        print_banner()
        print_menu()
        try:
            choice = input(colorize("请输入编号> ", ANSI_BLUE)).strip()
        except EOFError:
            print()
            return 0
        if choice == "0":
            print(colorize("已退出。", ANSI_BLUE))
            return 0
        try:
            run_choice(choice)
        except PermissionError as exc:
            print_error(f"错误：没有写入权限：{exc}")
            print_error(_permission_hint())
        except SandToolError as exc:
            print_error(f"错误：{exc}")
        except KeyboardInterrupt:
            print()
            return 0
        except Exception as exc:
            print_error(f"未预期错误：{exc}")
        print()


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_console()
    args_list = list(sys.argv[1:] if argv is None else argv)
    try:
        _platform_name()
        if not args_list:
            return interactive_loop()

        print_banner()
        args = build_parser().parse_args(args_list)
        if args.command == "set-path":
            result = apply_set_path(args.path)
            print_success("✓ Cursor 路径已保存")
            return result

        layout = resolve_cursor_layout()
        if args.command == "install":
            result = install(layout, args.transport)
            label = _stream_transport_label(args.transport)
            print_success(f"✓ Stream 模式已启用（{label}），Cursor 已重新启动")
            return result
        if args.command == "uninstall":
            result = uninstall(layout)
            print_success("✓ 已恢复 Cursor 原版，Cursor 已重新启动")
            return result
        if args.command == "move-exec-check":
            return cmd_move_exec_check(layout)
        if args.command == "move-exec-apply":
            return cmd_move_exec_apply(layout)
        if args.command == "move-exec-restore":
            return cmd_move_exec_restore(layout)
        if args.command == "ttft-check":
            return cmd_ttft_check(layout)
        if args.command == "ttft-apply":
            return cmd_ttft_apply(layout)
        if args.command == "ttft-restore":
            return cmd_ttft_restore(layout)
        if args.command == "ttft-sync":
            return cmd_ttft_sync(layout)
        if args.command == "rules-skills-check":
            return cmd_rules_skills_check(layout)
        if args.command == "machine-id-check":
            return cmd_machine_id_check(layout)
        if args.command == "machine-id-restore":
            return cmd_machine_id_restore(layout)
        raise SandToolError(f"未知命令：{args.command}")
    except PermissionError as exc:
        print_error(f"错误：没有写入权限：{exc}")
        print_error(_permission_hint())
        return 3
    except SandToolError as exc:
        print_error(f"错误：{exc}")
        return 2
    except KeyboardInterrupt:
        print_error("操作已取消。")
        return 130
    except Exception as exc:
        print_error(f"未预期错误：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
