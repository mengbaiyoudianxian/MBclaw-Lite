<!--
所有字段必填。空字段 = PR 立即关闭。
读 AGENTS.md 再开 PR。
-->

## Task ID
`[T*.*]`

## What changed（≤3 句）


## Affected files（每个文件 + 行数变化）
<!-- 例如:
- app/db.py: +78 -0
- tests/unit/test_db.py: +42 -0
-->


## Tests added/modified
<!-- 例如:
- tests/unit/test_db.py::test_init_creates_db
- tests/unit/test_db.py::test_pragma_wal
-->


## Local verification（粘贴命令输出）
```
$ pytest tests/unit -q
...
$ find app -name '*.py' | xargs wc -l | tail -1
```

## DoD Checklist（每项必须勾选）

- [ ] commit 标题前缀 `[T*.*]`
- [ ] 未引入新依赖（或已在 Design 仓 issue 批准，链接：）
- [ ] 单测覆盖本任务，且本地 pytest 全绿
- [ ] 文件行数符合 DEV-PLAN-r0 的 `≤N 行` 约束
- [ ] 未在 `api.py` / `pipeline.py` 直 import 模型表（必须走 `MemoryRepo`）
- [ ] e2e 测试断言阈值未改
- [ ] 未触发 CI 禁用清单（langchain/chromadb/celery/redis 等）

## 任何偏离 DEV-PLAN 的地方（如有）
<!-- 描述并附理由。CTO 决定接受或要求改回。 -->


## Related Memory entries（如有失败 / 否决归档）
<!-- 例如:
- MBclaw-Memory/experiments/failed/2026-06-22_xxx.md
-->
