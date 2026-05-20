#!/bin/bash
# Claude Code Status Line - uses Python for JSON parsing (no jq dependency)
export PYTHONIOENCODING=utf-8

# 修改为你的 Python 路径
# Windows 用户示例: PYTHON="C:/Users/YOUR/AppData/Local/Programs/Python/Python314/python.exe"
# macOS/Linux 用户: PYTHON="python3"
PYTHON="python3"

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
