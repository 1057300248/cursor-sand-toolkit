from .marker_doctor import MarkerFeature, MarkerRequirement

WORKBENCH_DESKTOP = "out/vs/workbench/workbench.desktop.main.js"
WORKBENCH_GLASS = "out/vs/workbench/workbench.glass.main.js"
AGENT_EXEC = "extensions/cursor-agent-exec/dist/main.js"
AGENT_HOST_675 = "extensions/cursor-agent-host/dist/675.js"


DEFAULT_DIAGNOSTIC_FEATURES: tuple[MarkerFeature, ...] = (
    MarkerFeature(
        id="performance.ttft",
        description="First-token timeout marker",
        requirements=(
            MarkerRequirement(WORKBENCH_DESKTOP, ("/*SAND_TTFT_V1*/",)),
            MarkerRequirement(
                WORKBENCH_GLASS,
                ("/*SAND_TTFT_V1*/",),
                optional_target=True,
            ),
        ),
        required=False,
    ),
    MarkerFeature(
        id="context.rules-skills",
        description="Rules/Skills activation marker",
        requirements=(
            MarkerRequirement(AGENT_EXEC, ("/*SAND_RULES_SKILLS_V4*/",)),
        ),
        required=False,
    ),
    MarkerFeature(
        id="context.user-rules",
        description="User/Team rules injection marker",
        requirements=(
            MarkerRequirement(WORKBENCH_DESKTOP, ("/*SAND_USER_RULES_V1*/",)),
            MarkerRequirement(
                WORKBENCH_GLASS,
                ("/*SAND_USER_RULES_V1*/",),
                optional_target=True,
            ),
        ),
        required=False,
    ),
    MarkerFeature(
        id="context.mcp-filesystem",
        description="MCP filesystem prompt marker",
        requirements=(
            MarkerRequirement(AGENT_HOST_675, ("/*SAND_MCP_FILESYSTEM_V1*/",)),
        ),
        required=False,
    ),
)
