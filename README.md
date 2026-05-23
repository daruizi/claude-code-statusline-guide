# Claude Code Status Line 配置指南

为 Claude Code CLI 配置一个信息丰富的底部状态栏，实时显示模型、目录、Git 分支、上下文用量、Token 统计、速率限制和日花费。

## 效果预览

```
Claude Opus 4.7 | ~/projects/my-app | main* | Context: 42% [████░░░░░░] | Tokens: 84.5K | 5h: 30% (2h15m)
```

显示内容：

| 项目 | 说明 |
|------|------|
| **Model** | 当前使用的模型名称 |
| **目录** | Claude Code 当前工作目录，HOME 缩为 `~` |
| **Git 分支** | 当前分支名，有未提交改动时标 `*`（非 git 目录自动隐藏） |
| **Context** | 上下文使用百分比 + 10 格进度条 |
| **Tokens** | 会话累计 input token 数（K/M 格式化） |
| **5h** | 5 小时速率限制使用率 + 重置倒计时 |
| **Cost** | 当日 API 花费（需可选 hook，未启用时自动隐藏） |

## 前置要求

- **Python 3.x**（用于解析 JSON，替代 `jq`）
- **Git**（可选，非 git 目录自动跳过）

> 不再依赖 bash —— 直接由 Claude Code 调用 Python。

## 安装步骤

### 第 1 步：创建状态栏脚本

在 `~/.claude/statusline.py` 创建：

```python
#!/usr/bin/env python3
"""Claude Code status line. Reads JSON on stdin, prints one line on stdout."""
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def progress_bar(pct: float, width: int = 10) -> str:
    filled = round(pct * width / 100)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def short_cwd(cwd: str) -> str:
    home = os.path.expanduser("~").replace("\\", "/")
    norm = cwd.replace("\\", "/")
    if norm.startswith(home):
        return "~" + norm[len(home):]
    parts = norm.rstrip("/").split("/")
    return ".../" + "/".join(parts[-2:]) if len(parts) > 2 else norm


def git_segment(cwd: str) -> str:
    """Return ' branch' or ' branch*', or '' if not a git working tree."""
    p = Path(cwd)
    for candidate in [p, *p.parents][:6]:
        if (candidate / ".git").exists():
            break
    else:
        return ""

    try:
        out = subprocess.check_output(
            ["git", "-C", cwd, "status", "--branch", "--porcelain=v2"],
            stderr=subprocess.DEVNULL, text=True, timeout=1,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""

    branch, dirty = "", False
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            branch = line.split(" ", 2)[2]
        elif line and not line.startswith("#"):
            dirty = True
    if not branch or branch == "(detached)":
        return ""
    return f"{branch}{'*' if dirty else ''}"


def daily_cost() -> str:
    p = Path.home() / ".claude" / "daily_cost.json"
    if not p.exists():
        return ""
    try:
        return json.loads(p.read_text()).get(date.today().isoformat(), "")
    except (json.JSONDecodeError, OSError):
        return ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data = {}

    model = data.get("model", {}).get("display_name", "Unknown")
    cwd = (
        data.get("workspace", {}).get("current_dir")
        or data.get("cwd")
        or os.getcwd()
    )

    ctx = data.get("context_window", {}) or {}
    used_pct = ctx.get("used_percentage")
    used_tokens = ctx.get("total_input_tokens")

    rl = data.get("rate_limits", {}).get("five_hour", {}) or {}
    five_pct = rl.get("used_percentage")
    five_reset = rl.get("resets_at")

    remaining = ""
    if five_reset:
        delta = int(five_reset) - int(datetime.now().timestamp())
        if delta > 0:
            h, m = delta // 3600, (delta % 3600) // 60
            remaining = f"{h}h{m}m" if h else f"{m}m"

    out = [model, short_cwd(cwd)]

    branch = git_segment(cwd)
    if branch:
        out.append(branch)

    if used_pct is not None:
        out.append(f"Context: {round(float(used_pct))}% {progress_bar(float(used_pct))}")

    if used_tokens:
        out.append(f"Tokens: {fmt_tokens(int(used_tokens))}")

    if five_pct is not None:
        seg = f"5h: {round(float(five_pct))}%"
        if remaining:
            seg += f" ({remaining})"
        out.append(seg)

    cost = daily_cost()
    if cost:
        out.append(f"Cost: ${cost}")

    sys.stdout.write(" | ".join(out))


if __name__ == "__main__":
    main()
```

### 第 2 步：配置 settings.json

直接由 Claude Code 调用 Python，不经 bash。

**Windows**：

```json
{
  "statusLine": {
    "type": "command",
    "command": "C:/Python314/python.exe C:/Users/YOUR_USER/.claude/statusline.py"
  }
}
```

> 用 `where python` 查 Python 实际路径。

**macOS / Linux**：

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py"
  }
}
```

### 第 3 步：验证

```bash
echo '{"model":{"display_name":"Claude Opus 4.7"},"workspace":{"current_dir":"/Users/me/code/demo"},"context_window":{"used_percentage":42.3,"total_input_tokens":84500},"rate_limits":{"five_hour":{"used_percentage":30}}}' | python ~/.claude/statusline.py
```

预期输出：

```
Claude Opus 4.7 | .../code/demo | Context: 42% [████░░░░░░] | Tokens: 84.5K | 5h: 30%
```

重启 Claude Code 即可看到状态栏。

## 自定义

| 想做什么 | 改哪里 |
|----------|--------|
| 关闭进度条 | 删 `Context: ...` 那行 |
| 改进度条宽度 | `progress_bar(used_pct, width=20)` |
| 改目录显示层级 | `short_cwd` 内 `parts[-2:]` → `parts[-3:]` |
| 隐藏某一段 | 注释掉对应 `out.append(...)` |

## 成本跟踪（可选）

`Cost` 段读取 `~/.claude/daily_cost.json`，格式：

```json
{ "2026-05-23": "1.23" }
```

文件不存在或当日无记录时，该段**自动隐藏**（不再显示 `Cost: $0.00`）。如需自动累加，配置 `PostToolUse` hook 写入该文件。

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 状态栏不显示 | settings.json 未配置或路径错误 | 确认 `statusLine.command` 存在且能直接运行 |
| 提示 jq not found | 用了旧版脚本 | 改用本指南的 Python 脚本，无需 jq |
| Python 找不到 | 路径错误 | `where python` / `which python` 查实际路径写入 settings.json |
| 目录显示成 `~` 或 `.claude` | 用了 `os.getcwd()` 而非 stdin 的 `workspace.current_dir` | 使用本指南的脚本（已修复） |
| Tokens 一直为 0 | 旧版读 `current_usage.input_tokens` 字段已废弃 | 本指南读 `context_window.total_input_tokens`（已修复） |
| 进度条字符歪斜 | 终端字体不支持 `█░` 等宽渲染 | 换 Nerd Font / Cascadia Code 等等宽字体，或改用 `#-` 等 ASCII 字符 |
| 状态栏刷新慢 | 旧版每次刷新 `bash → python → git × 2` | 本指南直接调 Python、git 合并为一次调用、非 git 目录短路（已优化） |

## 相比旧版的改进

| 类别 | 改进 | 影响 |
|------|------|------|
| **正确性** | 用 stdin `workspace.current_dir` 替代 `os.getcwd()` | 目录段反映 Claude Code 实际工作目录，而非脚本启动目录 |
| **正确性** | 用 `context_window.total_input_tokens` 替代已废弃的 `current_usage.input_tokens` | Tokens 段恢复显示 |
| **性能** | 去掉 bash 包装，Claude Code 直接调 Python | Windows 下省一层进程启动（~100–300ms / 刷新） |
| **性能** | `git status --branch --porcelain=v2` 一次拿分支 + dirty | 减少一次 git subprocess |
| **性能** | 非 git 目录通过 `.git` 路径检查短路 | 跳过 subprocess fork |
| **健壮性** | 裸 `except:` → 具体异常类型 | 真出 bug 时能定位 |
| **健壮性** | git subprocess 加 `timeout=1` | 卡死的 git 不会拖死状态栏 |
| **健壮性** | 沿父目录向上查找 `.git`（最多 6 层） | 项目子目录也能正确识别 git |
| **健壮性** | Cost 为空时自动隐藏 | 没装 hook 时不显示假数据 |
