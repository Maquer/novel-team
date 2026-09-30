# Version: 0.1.0
import argparse
import logging

logger = logging.getLogger(__name__)
import re, os

G = open('/var/minis/memory/GLOBAL.md', encoding='utf-8').read()
errs = []
warns = []

m = re.search(r'## 三', G)
if m:
    end = G.find('## 四', m.start())
    section = G[m.start():end] if end > 0 else G[m.start():m.start()+2000]
    dirs = re.findall(r'skills/(\S+)/', section)
    registered = set(d.rstrip('/') for d in dirs)
    fs = set(os.listdir('/var/minis/skills'))
    # 方向一：磁盘上有、§三 没登记 —— 索引缺失，可发现性问题（旧版文案把它叫
    # "Missing skill dirs"，容易被读成"目录丢了"而当噪声忽略，实为真信号）
    unregistered = fs - registered
    if unregistered:
        warns.append('Skills on disk but NOT in §三: ' + str(sorted(unregistered)))
    # 方向二：§三 写了、磁盘没有 —— 幽灵条目。若同行标注了归档去向则降级为提示
    ghost = registered - fs
    for name in sorted(ghost):
        line = next((l for l in section.splitlines()
                     if 'skills/' + name + '/' in l), '')
        if 'archived-skills/' in line:
            # 只认「写明归档到哪个目录」这种强判据。不用 '归档' 关键词——它可能以
            # "不需要归档"/"未归档" 等语义出现，会把真幽灵静默放过。
            continue
        else:
            errs.append('§三 幽灵条目（登记了但磁盘没有）: ' + name)

m = re.search(r'## 五', G)
if m:
    end = G.find('## 六', m.start())
    section = G[m.start():end] if end > 0 else G[m.start():m.start()+3000]
    count = 0
    for line in section.splitlines():
        if line.startswith('|') and '`' in line:
            count += 1
    if count < 13:
        warns.append('Only ' + str(count) + ' model rows, expected 13')

m = re.search(r'## 六', G)
if m:
    end = G.find('## 七', m.start())
    section = G[m.start():end] if end > 0 else G[m.start():m.start()+8000]
    for line in section.splitlines():
        if '已丢失' in line:
            continue
        for path in re.findall('`(/var/minis/[^`]+)`', line):
            path = path.split(' ')[0].rstrip('-')
            if 'workspace' in path:
                continue
            if not os.path.exists(path):
                errs.append('File not found: ' + path)

m = re.search(r'## 八', G)
if m:
    end = G.find('## 九', m.start())
    section = G[m.start():end] if end > 0 else G[m.start():m.start()+2000]
    entries = [l for l in section.splitlines() if re.match(r'\|\s+\d{4}-\d{2}-\d{2}', l)]
    if len(entries) > 10:
        warns.append('Decisions ' + str(len(entries)) + ' > 10')

# minis-cli 版本：旧实现用 r'minis-cli.*?v(\d+\.\d+\.\d+)' 在全文匹配，会一路漂到
# 后面别的行抓到无关版本号（实测抓到 draw.io 的 31.4.6）；且期望值硬编码在脚本里，
# 工具一升级就恒假告警。改为：只在含 minis-cli 的那一行内取版本 + 与实跑输出比对。
import subprocess
mc_disk = None
try:
    out = subprocess.run(['/var/minis/shared/minis-cli', '--version'],
                         capture_output=True, text=True, timeout=20).stdout
    mv = re.search(r'v(\d+\.\d+\.\d+)', out)
    mc_disk = mv.group(1) if mv else None
except Exception as e:
    warns.append('minis-cli --version 取不到: %s（跳过版本核对）' % type(e).__name__)
for line in G.splitlines():
    if 'minis-cli' in line and '(v' in line:
        mv = re.search(r'\(v(\d+\.\d+\.\d+)\)', line)
        if mv and mc_disk and mv.group(1) != mc_disk:
            warns.append('minis-cli version stale in GLOBAL: 写的 v%s，实为 v%s'
                         % (mv.group(1), mc_disk))
        break
else:
    warns.append('GLOBAL 未标注 minis-cli 版本（应写作 minis-cli (vX.Y.Z)）')

if '已修复反馈层 8/8' not in G:
    warns.append('Feedback not marked fixed')
if '已修复知识存储 100%' not in G:
    warns.append('Knowledge store not marked fixed')

print('=' * 60)
print('  GLOBAL.md consistency check')
print('=' * 60)
for e in errs:
    print('  [ERR] ' + e)
for w in warns:
    print('  [WARN] ' + w)
print('=' * 60)
print('  Errors: ' + str(len(errs)))
print('  Warnings: ' + str(len(warns)))
if errs:
    exit(1)

def main():
    parser = argparse.ArgumentParser(description='TODO: 描述此脚本功能')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    args = parser.parse_args()
    print("TODO: 实现主要逻辑")


if __name__ == '__main__':
    main()
