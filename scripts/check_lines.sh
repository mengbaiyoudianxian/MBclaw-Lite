#!/usr/bin/env bash
# 检查 app/ 总行数与每文件预算
# 用法: ./scripts/check_lines.sh
set -e

TOTAL=$(find app -name '*.py' -not -name '__init__.py' | xargs cat | wc -l)
echo "app/ 总行数: $TOTAL / 1500"

if [ "$TOTAL" -gt 1500 ]; then
    echo "❌ 超出 MVP 预算（1500 行）"
    exit 1
fi

declare -A BUDGET=(
    [app/db.py]=80
    [app/models.py]=120
    [app/llm.py]=120
    [app/memory.py]=200
    [app/pipeline.py]=80
    [app/api.py]=300
    [app/main.py]=80
)

FAIL=0
for f in "${!BUDGET[@]}"; do
    [ -f "$f" ] || continue
    LINES=$(wc -l < "$f")
    MAX=${BUDGET[$f]}
    if [ "$LINES" -gt "$MAX" ]; then
        echo "❌ $f: $LINES 行（预算 $MAX）"
        FAIL=1
    else
        echo "✅ $f: $LINES / $MAX"
    fi
done

exit $FAIL
