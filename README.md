# Claude Code Status Line 配置指南

为 Claude Code CLI 配置一个信息丰富的底部状态栏，实时显示模型、目录、Git 分支、上下文用量、Token 统计、速率限制和日花费。

## 效果预览

```
Qwen 3.6 Plus | .../projects/my-app | main* | Context: 72%[███████░░░] | Tokens: 200.0K | 5h: 45% (2h15m) | Cost: $0.00
```

显示内容：
| 项目 | 说明 |
|------|------|
| **Model** | 当前使用的模型名称 |
| **目录** | 当前工作目录（缩短显示） |
| **Git 分支** | 当前分支名，有未提交改动时标 `*` |
| **Context** | 上下文使用百分比 + 10 格进度条 |
| **Tokens** | 会话 Token 总量（自动 K/M 格式化） |
| **5h** | 5 小时速率限制使用率 + 重置倒计时 |
| **Cost** | 当日 API 花费（需要成本跟踪脚本） |

## 前置要求

- **Python 3.x**（用于解析 JSON，替代 `jq`）
- **Git**（用于获取分支信息）
- **Bash**（Claude Code 内置）

## 安装步骤

### 第 1 步：创建状态栏脚本

在 `~/.claude/statusline-command.sh` 创建以下脚本：

```bash
#!/bin/bash
# Claude Code Status Line - uses Python for JSON parsing (no jq dependency)
export PYTHONIOENCODING=utf-8

# 修改为你的 Python 路径
PYTHON="python3"  # Windows 用户示例: "C:/Users/YOUR/AppData/Local/Programs/Python/Python314/python.exe"

$PYTHON -c "
import json, sys, os, subprocess, datetime

# Read JSON input from stdin
try:
    data = json.load(sys.stdin)
except:
    data = {}

model = data.get('model', {}).get('display_name', 'Unknown')

# Context window
ctx = data.get('context_window', {})
used_pct = ctx.get('used_percentage')
usage = ctx.get('current_usage', {})
input_tokens = usage.get('input_tokens', 0)
output_tokens = usage.get('output_tokens', 0)
total_tokens = input_tokens + output_tokens

def fmt_tokens(n):
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'
    elif n >= 1_000:
        return f'{n/1_000:.1f}K'
    return str(n)

# Progress bar
def progress_bar(pct):
    if pct is None:
        return ''
    filled = round(pct / 10)
    empty = 10 - filled
    return '[' + '█' * filled + '░' * empty + ']'

# Rate limits
rl = data.get('rate_limits', {}).get('five_hour', {})
five_hour_pct = rl.get('used_percentage')
five_hour_reset = rl.get('resets_at')

remaining = ''
if five_hour_reset:
    delta = five_hour_reset - int(datetime.datetime.now().timestamp())
    if delta > 0:
        h, m = delta // 3600, (delta % 3600) // 60
        remaining = f'{h}h{m}m' if h > 0 else f'{m}m'

# Daily cost
cost_file = os.path.expanduser('~/.claude/daily_cost.json')
today = datetime.date.today().isoformat()
try:
    with open(cost_file) as f:
        daily_cost = json.load(f).get(today, '0.00')
except:
    daily_cost = '0.00'

# Current working directory (shortened)
cwd = os.getcwd()
parts = cwd.replace('\\\\', '/').split('/')
if len(parts) > 2:
    cwd_display = '.../' + '/'.join(parts[-2:])
else:
    cwd_display = cwd

# Git branch
try:
    git_branch = subprocess.check_output(
        ['git', 'branch', '--show-current'],
        stderr=subprocess.DEVNULL, text=True
    ).strip()
    if git_branch:
        dirty = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        git_branch = f' | {git_branch}' + ('*' if dirty else '')
    else:
        git_branch = ''
except:
    git_branch = ''

# Build output
parts_out = [model, f'{cwd_display}']
if git_branch:
    parts_out.append(git_branch.lstrip(' | '))
if used_pct is not None:
    parts_out.append(f'Context: {used_pct}%{progress_bar(used_pct)}')
if total_tokens > 0:
    parts_out.append(f'Tokens: {fmt_tokens(total_tokens)}')
if five_hour_pct is not None:
    rl_str = f'5h: {five_hour_pct}%'
    if remaining:
        rl_str += f' ({remaining})'
    parts_out.append(rl_str)
parts_out.append(f'Cost: \${daily_cost}')

print(' | '.join(parts_out))
"
```

> **重要**：Windows 用户需要将 `PYTHON` 变量改为 Python 的完整路径，例如：
> ```bash
> PYTHON="C:/Users/YOUR/AppData/Local/Programs/Python/Python314/python.exe"
> ```
> 可通过 `where python` 或 `which python` 查看路径。

### 第 2 步：配置 settings.json

在 `~/.claude/settings.json` 中添加（或合并到已有配置中）：

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash \"$HOME/.claude/statusline-command.sh\""
  }
}
```

### 第 3 步：验证

重新打开 Claude Code，底部应出现状态栏。也可手动测试脚本：

```bash
echo '{"model":{"display_name":"Test"},"context_window":{"used_percentage":50,"current_usage":{"input_tokens":10000,"output_tokens":5000}},"rate_limits":{"five_hour":{"used_percentage":20,"resets_at":null}}}' | bash ~/.claude/statusline-command.sh
```

## 自定义

### 修改显示内容

编辑 `statusline-command.sh` 中 `# Build output` 部分，增删 `parts_out.append()` 行即可。

### 修改进度条宽度

修改 `progress_bar` 函数中的 `10`（10 格）为其他数字。

### 修改目录缩短规则

修改 `cwd_display` 相关逻辑，调整 `parts[-2:]` 中的 `-2` 来控制显示几级目录。

### 关闭某项信息

注释掉对应行即可，例如不显示 Cost：

```python
# parts_out.append(f'Cost: \${daily_cost}')
```

## 成本跟踪（可选）

Status Line 的 Cost 字段读取 `~/.claude/daily_cost.json`，格式如下：

```json
{
  "2026-05-20": "1.23",
  "2026-05-21": "2.50"
}
```

可在 `PostToolUse` hook 中调用脚本自动累加花费，也可以手动维护。

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 状态栏不显示 | settings.json 未正确配置 | 确认 `statusLine` 字段存在 |
| 输出乱码 | 编码问题 | 确保 `PYTHONIOENCODING=utf-8` |
| jq: command not found | 系统未安装 jq | 本脚本已用 Python 替代，无需 jq |
| Python 找不到 | 路径错误 | 修改 `PYTHON` 变量为正确路径 |
| Git 分支不显示 | 不在 git 仓库中 | 正常行为，非 git 目录不显示分支 |
