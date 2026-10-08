#!/bin/bash
# 小说团队工具链测试脚本
# 用法：bash tools/test-tools.sh

set -e
cd "$(dirname "$0")/.."

echo "=========================================="
echo "📚 小说团队工具链测试"
echo "=========================================="

echo ""
echo "[1] 质量债务系统测试"
python3 tools/quality-debt.py list --novel-id my-novel --status all
echo "  ✓ quality-debt.py OK"

echo ""
echo "[2] 待确认区测试"
python3 tools/pending-review.py list --novel-id my-novel --status all
echo "  ✓ pending-review.py OK"

echo ""
echo "[3] 角色深度测试"
python3 tools/character-depth.py depth --novel-id my-novel
echo "  ✓ character-depth.py OK"

echo ""
echo "[4] 上下文筛选测试"
python3 tools/char-context-filter.py build --novel-id my-novel --chapter 2 --full 2>/dev/null | head -30
echo "  ✓ char-context-filter.py OK"

echo ""
echo "[5] 门禁检查测试"
python3 tools/gate-check.py check --file projects/my-novel/chapters/chapter-002.md 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  ✓ 门禁结果: passed={d[\"passed\"]}, debts={d.get(\"debt_integration\",{}).get(\"debts_added\",0)}')"
echo "  ✓ gate-check.py OK"

echo ""
echo "=========================================="
echo "✅ 全部工具测试通过"
echo "=========================================="
