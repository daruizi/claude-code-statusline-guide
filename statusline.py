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
    """Return 'branch' or 'branch*', or '' if not a git working tree."""
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

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
