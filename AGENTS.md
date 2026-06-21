# AGENTS.md（main 分支告示）

> **不要在 main 分支动任何代码。**
> 所有开发在 **r0 分支** 进行。

```bash
git checkout r0
```

切到 r0 后阅读：
1. r0 分支的 `AGENTS.md` —— 6 条铁律 + 工作流
2. r0 分支的 `PROMPTS-FOR-EXECUTORS.md` —— 提示词集
3. https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/roadmap/DEV-PLAN-r0.md —— 任务清单

## 为什么 main 分支保留旧代码？

main 是 R0 冻结前的版本（10379 行 / 39 services），保留作历史参考。
不会再合任何 PR 到 main，除非 R1 ship 时把 r0 整体合入。

---

## 历史 AGENTS.md（v0，已作废）

下文为 R0 冻结前的旧版描述，**全部已被否决或延期至 R2+**：MEMORY.md 双态 / SkillCard / Curator / 写入审批门多维 / 外部漂移检测。
保留只为说明：**不要按这些内容实现任何东西**。详见 r0 分支的 AGENTS.md 与 DEV-PLAN-r0.md。
