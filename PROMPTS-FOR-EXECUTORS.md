# 给执行 AI 的提示词集

> 直接复制粘贴喂给 OpenHands / Claude Code / 任何执行 AI。
> 每个提示词都是**独立可用**的——不需要额外解释。

---

## 提示词 1：启动 OpenHands（首次接手）

```
你是 MBclaw R0 阶段的代码执行者。

第一件事：克隆并阅读以下 3 个文件，全部读完后告诉我你理解了什么。

1. https://github.com/mengbaiyoudianxian/MBclaw-Lite/blob/main/AGENTS.md
2. https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/roadmap/DEV-PLAN-r0.md
3. https://github.com/mengbaiyoudianxian/MBclaw/blob/main/design/mvp/MVP-r0-1week.md

读完后回答 4 个问题：
A. 你的 6 条铁律是什么？
B. 你的第一个任务编号是什么？文件路径与行数预算是什么？
C. 你不允许引入哪些 Python 依赖？
D. 你完成一个任务的标准工作流是什么（编号步骤）？

回答正确后我才允许你动手。
```

---

## 提示词 2：执行单个任务（每个 T*.* 一次）

```
任务: 执行 DEV-PLAN-r0.md 中的 T{X.Y}。

规则：
- 不要读其他任务，专注 T{X.Y}
- 按"步骤"严格实现，参考"必含"小节
- 写"验证"中描述的测试
- 不超过行数预算
- 不引入禁用依赖
- 不改 e2e 断言

完成后：
1. 本地运行：
   pytest tests/unit -q
   find app -name '*.py' -not -name '__init__.py' | xargs wc -l | tail -1
2. 把输出贴在 PR 描述里
3. 按 .github/pull_request_template.md 填写 PR
4. commit 标题以 [T{X.Y}] 开头

如果遇到障碍，参考 AGENTS.md §6 的 4 种情况，不要擅自决策。
```

---

## 提示词 3：M1 归档旧 services（一次性脚本）

```
任务: MBclaw-Memory/drafts/2026-06-21_legacy-services-to-be-extracted.md 中列出的 14 个旧 services 物理迁移到 MBclaw-Memory 仓。

步骤：
1. 克隆两个仓库：
   MBclaw-Lite (main 分支)
   MBclaw-Memory (main 分支)
2. 对每个源文件：
   a. cp Lite/app/services/<file>.py → Memory/drafts/legacy/<分类>/<file>.py
   b. 在每个迁出文件顶部加注释：
      # 归档自 MBclaw-Lite@<commit-hash>, 路径 app/services/<file>.py
      # 移出原因：见 MBclaw-Memory/decisions/rejected/ 或 MBclaw/design/audit/SURVIVAL-REVIEW-2026-06-21.md
      # R0 状态：移出 Core；R2 重启或永久放弃见上述文档
3. 不修改任何代码内容
4. 同步归档对应的 routers/{file}.py 与 models/{file}.py（如有）
5. 在 Memory/drafts/legacy/README.md 写迁出清单（文件名 + 源 hash + 分类）
6. 提交：
   Memory: "M1: 归档 14 个旧 services 至 drafts/legacy/"

约束：
- 不准修改 Lite 仓（M1 只读 Lite，写 Memory）
- 不准跳过任何文件
- 不准合并文件

完成后给我：迁出文件数、目录树、提交 hash。
```

---

## 提示词 4：每天结束的自检（让执行 AI 自我审计）

```
每天结束时自查：

1. 今天合并了几个 PR？每个的 commit 标题是？
2. 今天有没有任何 PR 行数超预算？
3. 今天有没有引入任何新依赖？
4. tests/unit 与 tests/e2e 是否仍全绿？
5. find app -name '*.py' -not -name '__init__.py' | xargs wc -l | tail -1 输出是？
6. 进度：完成了哪些 T*.*？还剩哪些？

把结果贴到 MBclaw-Memory/logs/YYYY-MM-DD_daily-report.md。
```

---

## 提示词 5：遇到设计文档自相矛盾时

```
我在执行 T{X.Y} 时发现文档冲突：
- 文档 A 说 ...
- 文档 B 说 ...

按 AGENTS.md §6 情况 B，我现在：
1. 暂停当前 PR
2. 创建 MBclaw-Memory/experiments/failed/YYYY-MM-DD_doc-conflict-T{X.Y}.md，记录冲突
3. 在 MBclaw 仓 issue 描述冲突，@CTO

不擅自决策。等待裁决。
```

---

## 提示词 6：CTO 视角的 PR review（给另一个 AI 用，不是执行者用）

```
你是 MBclaw 的 CTO（评审者）。

下面是一个待 review 的 PR，请按 AGENTS.md §2 的 6 条铁律 + DEV-PLAN-r0.md 中对应任务的"不允许"清单逐项检查：

[贴 PR 链接或 diff]

输出格式：
- ✅ / ❌ 铁律 1：commit 标题前缀
- ✅ / ❌ 铁律 2：requirements
- ✅ / ❌ 铁律 3：单测
- ✅ / ❌ 铁律 4：行数预算（具体数字）
- ✅ / ❌ 铁律 5：MemoryRepo
- ✅ / ❌ 铁律 6：e2e 阈值
- ✅ / ❌ 任务特定"不允许"清单（逐条）
- ✅ / ❌ 测试覆盖
- ✅ / ❌ PR 描述完整

任一 ❌ → 给出 reject 评论 + 具体修改建议。
全部 ✅ → 给出 approve 评论。
```

---

## 提示词 7：触发 R2 信号时（暂时不需要，留作未来）

```
我观察到以下信号：
- [具体信号 + 实测数据]

按 DEV-PLAN-r0 §7（完整路线图）的 R2 触发条件对照：
- [对应的 R2 项目]

我建议：
1. 在 MBclaw 仓开 issue 描述信号 + 实测数据
2. CTO 评审，决定是否启动该 R2 项目
3. 若启动，先在 MBclaw/design/ 写设计稿，再开发

不擅自启动 R2 项目。
```

---

## 使用建议

1. **首次启动**：用提示词 1，确认理解
2. **逐任务执行**：每天用提示词 2，一次一个任务
3. **并行归档**：找一个 AI 用提示词 3 跑 M1
4. **每天结束**：用提示词 4 自检
5. **遇到冲突**：用提示词 5
6. **代码 review**：另一个 AI 用提示词 6
7. **R1 ship 后**：用提示词 7 监控 R2 信号

---

## 红线（提示词永远不会让你做的事）

- 删除任何文件 in main 分支（main 是 R0 冻结的参考基准）
- 修改任何 design/ 下的文档（除非 CTO 在 PR review 中要求）
- 修改任何 MBclaw-Memory/decisions/rejected/ 下的文件（已成定论）
- push 到 main 分支（所有 PR 走 r0 分支）
- skip CI（即使 CI 出 bug 也不绕过）
