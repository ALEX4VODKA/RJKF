# Git 工作流规范

目标：让 Git 历史**真实、清楚、可追溯**，能展示项目怎样逐步完成；同时让我理解每次 Git 操作，而不是只让 Codex 代劳。

## 1. 工作流程

对功能开发和 Bug 修复，默认采用：

```text
确认需求与现有代码 → 检查 Git 状态 → 创建/切换功能分支
→ 小步实现 → 验证功能 → 检查改动 → 提交 Commit
→ 推送分支 → 创建 PR → 检查后合并 main
```

- `main` 保持可运行；**不要直接在 `main` 上开发功能**。
- 一个分支围绕一个功能或明确的问题，不按“每天”机械建分支。
- 已存在的分支、未提交改动和队友 A 的成果应先检查、保护，不能擅自覆盖。
- 一次完整功能可以有多个 Commit；通过一个 PR 合并即可。纯本地探索尚不需要 PR，正式合并到远端 `main` 时优先使用 PR。

常用分支名（英文短词）：

```text
feat/parking-record
feat/billing
feat/recognition
feat/report
fix/exit-flow
docs/run-guide
```

## 2. Commit 规范

使用 Conventional Commits：

```text
<type>(<scope>): <简短说明>
```

常用 `type`：`feat` 新功能、`fix` 修复、`refactor` 不改变行为的重构、`test` 测试、`docs` 文档、`chore` 工程维护。

本项目示例：

```text
feat(db): 建立停车记录与收费规则表
feat(billing): 实现按时长计费与每日封顶
feat(control): 实现车辆进场登记与重复校验
fix(control): 修复未缴费车辆错误放行
feat(report): 增加月度统计与 PDF 导出
test(billing): 覆盖免费时长和跨天计费场景
```

- **一次提交解决一个明确的逻辑问题**，不要把互不相关的改动打包。
- 不为“原子化”强行拆成大量琐碎 Commit；也不要积攒到整个项目完成才提交一次。
- 只提交真实完成的内容，不伪造开发历史、作者、时间、测试结果或阶段。
- Commit 信息说明**发生了什么变化**，避免 `update`、`fix bug`、`完成项目` 等空泛描述。

## 3. 提交前检查

```bash
git status -sb
git diff
git diff --stat
```

只暂存本次相关的文件；需要拆分同一文件中的改动时可用 `git add -p`：

```bash
git add <file>
git diff --cached
git diff --cached --check
```

提交前确认：

1. 本次改动目的明确；没有混入 A 的无关代码或其他任务修改。
2. 相关功能和测试已验证；未运行的测试必须如实说明。
3. 暂存区没有 `.env`、密码、Token、真实个人数据、数据库运行文件、日志、缓存或无关生成物。
4. `git diff --cached` 展示的内容，就是准备提交的内容。

除非明确确认暂存范围，否则不要直接执行 `git add .`。

## 4. PR 与合并

一个可演示的功能阶段完成后，优先创建一个 PR。PR 描述保持简短：

```text
目的：解决什么问题
主要改动：做了什么
验证：运行了哪些测试、结果如何
注意：尚未解决的问题或兼容性影响
```

- 合并前检查 PR diff、测试和与 `main` 的冲突。
- Merge 或 Squash 依项目需要选择；不要为“漂亮历史”抹掉真实贡献或编造过程。
- 不擅自 Force Push、改写共享分支历史，或使用 `reset --hard`、`clean -fd` 等可能丢失工作成果的操作。

## 5. Codex 的 Git 权限边界

Codex 可以检查状态、建功能分支、编写代码、执行测试、查看 diff、提出 Commit/PR 方案。

**未经我明确确认，不执行 Commit、Push、创建/合并 PR、删除分支或破坏性 Git 操作。** 如当前任务另有明确授权，以当次授权为准。

申请提交时只需要报告：

```text
改动目的：
主要修改文件：
验证结果：
准备暂存的文件：
建议 Commit：
```

同时简要解释本次 Git 操作的作用；不要仅输出一串命令让我照抄。

> 核心原则：Git 历史先求真实，再求整洁；每个 Commit 都应回答“这次修改解决了什么问题？”
