# Git 版本控制与可追溯规则

## 目的

AgentLoop 对项目的修改必须由实际版本控制记录，不依赖 AI 对旧内容的记忆、聊天记录或重新生成来回滚。

本规则适用于代码、配置、数据库脚本、接口契约、项目内文档、测试和自动化脚本。

## 强制入口检查

在第一次写入项目文件前必须执行：

```text
确定准确的 project_root
→ 检查 project_root 是否由有效 Git 仓库管理
    ├── 已管理
    │   → 记录 git_root、当前分支、HEAD 和工作区状态
    └── 未管理
        → 检查忽略规则和敏感文件
        → 展示将进入初始提交的文件和风险
        → 通过 repository_bootstrap Gate
        → git init
        → 建立初始基线提交
        → 记录 baseline_commit
→ 基线可追溯后才允许修改项目文件
```

如果项目属于明确的父级仓库或 monorepo，并且该仓库实际跟踪项目目录，不得在子目录重复初始化嵌套仓库。

## 非 Git 项目的初始化

项目不在任何有效 Git 仓库中时，Agent 必须：

1. 在不写入项目的前提下检查准备纳入仓库的目录、敏感文件和大文件。
2. 向用户展示初始提交范围和风险，通过 `repository_bootstrap` Gate。
3. 在准确的项目根目录执行 `git init`。
4. 检查并补充 `.gitignore`。
5. 排除密钥、凭据、本地配置、构建结果、缓存、依赖目录和大文件。
6. 再次查看准备纳入基线的文件，禁止直接盲目提交全部文件。
7. 对已授权且确认安全的现有项目内容建立初始提交。
8. 将初始提交 SHA 保存为 `baseline_commit`。

没有初始基线提交时，仅执行 `git init` 不算完成，因为此时仍无法可靠恢复原始内容。

如果授权未通过、缺少 Git 身份、存在敏感文件或无法判断文件归属，状态进入 `blocked`，不得继续修改项目文件。仓库初始化要求保留，但初始提交不得在未检查和未授权时自动执行。

## 已有 Git 项目的基线

开始修改前必须保存：

```yaml
git:
  root:
  target_branch:
  branch:
  worktree:
  head_commit:
  working_tree_status:
  baseline_commit:
```

`baseline_commit` 默认等于开始任务时的 `HEAD`。

如果工作区已有未提交变化：

- 默认视为用户已有工作，不得删除、覆盖、重置或私自提交。
- 与本次任务无关时，记录状态后避开这些文件。
- 与本次任务修改范围重叠时，必须先让现有变化形成可恢复基线，或由用户决定如何处理。
- 不得通过 `git reset --hard`、`git clean -fd` 等方式制造干净工作区。

## AgentLoop 修改记录

每个可独立完成的开发切片在 `loop.yaml.git.checkpoints` 至少记录：

```yaml
- subflow_id:
  requirement_version:
  before_commit:
  changed_files:
  checks_run:
  after_commit:
```

修改应形成小而明确的提交。提交信息建议使用：

```text
agentloop(<loop_id>/<subflow_id>@r<requirement_version>): <本次开发切片完成的结果>
```

一个提交只包含当前开发切片的相关变化，不混入用户已有修改或无关格式化。

## 多 Loop 与并发

没有其他活动 Loop、范围不冲突、目标分支不受保护且用户已有修改不重叠时，trivial/standard 可以复用当前分支和工作树。两个非终态 Loop 或子流程并发修改项目时，单独的 Loop 锁不够，开始前必须：

```text
声明 paths/interfaces/db_objects/states 修改范围
→ 检查其他活动 Loop 的范围
→ 无冲突时使用独立分支和 worktree
→ 有冲突时建立依赖并顺序执行，或进入 blocked
```

不得让两个 Loop 在同一工作树中交错修改后再猜测提交归属。父子 Loop 和复合子流程的分支、worktree、范围和检查点记录在各自规范字段中。

## 复合 Loop 与同仓库 epic 的交付合并

复合 Loop 和同仓库 epic 使用一条独立集成分支和 worktree。切片或子 Loop 的交付提交不得直接合并到项目 `target_branch`。

```text
交付单元在 source_commit 上验证 passed/done
→ 协调者把 source_commit 加入 git.integration.merges
→ 按依赖顺序合并到 Loop 集成分支
→ 全部交付合并后，在集成 head 上按各单元的 targeted/flow 策略重跑检查
→ integration_verification.required == false
    → git.integration.status: verified
→ integration_verification.required == true
    → 形成 integration_verification.handoff
    → 在同一个 integration head 上执行跨交付验证
    → 通过后 git.integration.status: verified
```

默认使用项目配置的 `merge_no_ff`，保留切片提交历史。合并只能由 `owners.coordination` 在持有 Loop 锁和集成 worktree 时执行；协调者若要修改业务代码，必须切换为开发角色。

### 合并冲突

```text
合并产生冲突
→ 中止未完成的合并，集成工作树恢复到原 head
→ merges[].status: conflict
→ 保存冲突文件和相关切片
→ 受影响切片回到 developing
→ 开发 Agent 基于当前集成 head 解决冲突
→ 重新开发自检和切片验证
→ 产生新的 source_commit
→ 旧合并项 superseded，重新排队
```

协调者不得在没有开发验证的情况下直接解决冲突并继续。文本无冲突也可能有行为冲突，因此全部合并后必须在最终集成提交上按各交付单元的 `targeted/flow` 策略重跑检查；允许合并同一命令批量执行，但每个单元都要有结果归属。

同一合并项每次使用新的已验证 `source_commit` 重试时增加 `attempts`；达到 `max_attempts` 仍冲突则父 Loop `blocked`，不得无限反复合并。

合并后检查全部通过且不需要跨切片验证时，将 `git.integration.status` 设为 `verified`；需要跨切片验证时先设为 `ready_for_verification`，集成验证通过后再设为 `verified`。

### 集成提交与目标分支

`integration_verification.handoff.code_commit` 必须等于测试开始时的 `git.integration.head_commit`。测试期间该分支有新提交时，原集成证据立即失效并重新执行。

集成分支产生新的已测试提交后，协调者必须使用控制命令记录 checkpoint，不得直接编辑状态文件：

```bash
agentloop integration-checkpoint <loop-id> \
  --actor loop-coordinator \
  --reason "<本次集成检查>" \
  --evidence <当前提交上的 evidence-id>
```

命令只接受当前 Git HEAD、当前需求版本、父级集成 scope 且 `active/passed` 的 Evidence。子流程 Evidence、任意 targeted 检查或未声明执行器不能冒充集成验证。

`integration_verification.required: true` 时必须先按以下状态序执行：

```text
pending/failed
→ integration-transition ready_for_verification
→ integration-transition verifying
→ 执行 reused_flows + new_flows 中声明的全部集成 Flow
→ integration-checkpoint 精确校验 Flow 集合、executor、acceptance_id 和当前提交
→ passed
```

只有最后一步才原子更新 `git.integration.head_commit`、`delivery_commit`、`last_checkpoint_commit` 和集成 handoff。`required: false` 仍须用父级当前提交的合并后检查覆盖全部验收义务。旧提交、旧需求版本、子流程 scope、stale、failed、未知或能力不匹配的 Evidence 必须拒绝。

同仓库 epic 不要求子 Loop 先合并到项目 `target_branch`。父 Loop 直接把每个子 Loop 的已验证交付提交作为 `source_commit` 合并到父集成分支，因此子 Loop 可以继续使用默认的 `verified_integration_branch`。跨仓库 epic 不执行 Git 合并，只锁定各仓库交付提交。

```text
delivery_mode == verified_integration_branch
→ AgentLoop 以已验证 integration head 作为开发交付提交
→ 不在本 Loop 内合并项目 target_branch

delivery_mode == merge_to_target_after_verified
→ 协调者把已验证 integration head 合并到 target_branch
→ 记录 delivery_commit
→ target_branch 已前进或合并结果产生新内容时
    → 在 delivery_commit 上重跑合并后检查和集成验证
```

受保护分支需要的 PR 或人工批准仍是外部 Gate，不得绕过。无论采用哪种交付模式，最终交付都必须指向一个包含全部必需切片、且实际通过验证的精确提交。

## 提交时机

至少在以下节点形成 Git 检查点：

```text
非 Git 项目完成初始化
→ 初始基线提交

需求准备进入确认 Gate
→ 需求产物检查点
→ 审批摘要只绑定该检查点中的文件字节

一个可独立开发的切片完成开发自检
→ 开发提交

测试代码或流程定义发生新增、修改
→ 测试提交

测试失败后完成修复并重新通过开发自检
→ 修复提交
```

尚未通过开发自检的临时代码可以保留在工作区，但不能被标记为 `ready_for_verification`。

## 回滚规则

回滚必须依据 Git 记录：

```text
确认目标提交和影响文件
→ 查看实际 diff
→ 选择精确恢复或创建 revert 提交
→ 重新运行必要检查
→ 保存回滚提交和运行结果
```

优先使用可追溯的 `git revert` 撤销已经提交的 AgentLoop 变化。

恢复未提交文件前，必须确认文件中没有用户在基线之后产生的其他修改。禁止用 AI 记忆重写旧代码作为回滚方式。

## 需求变化与产物失效

需求版本变化时，不直接删除旧实现：

- 保留原提交和需求版本关系。
- 通过新提交修改或撤销受影响内容。
- 每个检查点记录 `requirement_version`。
- 在 `loop.yaml.artifacts` 中将受影响产物标记为 `stale` 或 `superseded`，并记录失效版本和原因。
- 在 `evidence.yaml` 中将受影响证据标记为 `stale`。
- 未受影响的提交继续复用。

## 完成条件

项目修改只有同时满足以下条件才可交给测试：

```text
项目由有效 Git 仓库管理
+ baseline_commit 已记录
+ 用户已有修改未被覆盖
+ 本次变化可以通过 diff 查看
+ 当前开发结果已经形成提交
+ 提交 SHA 已写入 AgentLoop 状态记录
```
