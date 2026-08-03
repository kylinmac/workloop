# Workloop：轻量认知质量控制循环

Workloop 只控制两件事：**认知质量**（想得对不对）和**验证真实性**（证据是不是外部的）。过程本身给 Agent 自由。旧 AgentLoop 协议（`agentloop/`）冻结不再修改，其自述结构（assumptions、decision_records、knowledge_state 等）的意图由 spec 假设表、独立 review、有上限的 memory 承接。

## 宪法（8 条，全部规则的上限）

1. **每个阶段有且只有一份固定产物**，全部是人可读可改的 Markdown。产物之外不产生任何控制文件。
2. **只认外部证据**。验证 = 命令的真实输出、真实截图、人的确认。Agent 的自我声明（"我已确认""应该没问题"）在任何阶段都不构成证据。这条同样约束 review：审查者身份必须有外部锚（子代理会话 ID、人的署名），无锚的 review 无效。
3. **阻塞假设未关闭，不得进入下一阶段**。关闭假设必须附证据（来源、命令输出或人的答复）。
4. **认知一致性校验必须由非执行视角完成**：一个未参与执行的干净上下文（子代理、新会话或人）拿 spec 对照 plan、diff 和证据做语义比对。执行者不能给自己的工作出具 review。
5. **任务小到一个干净上下文能完成**。装不下就拆成多个 loop，不引入新的流程状态来兜住复杂度。
6. **失败的处方只有两种**：新增一条可执行检查（测试/lint/命令），或简化流程。禁止第三种处方——"要求 Agent 多声明一件事"。
7. **错误记忆有硬上限**（20 条）。每条必须带触发条件和预防检查；新增时超限必须合并或淘汰。记不住的规则等于不存在。
8. **Agent 每轮加载的流程内容 = 本文件 + 入口 skill + 当前阶段 skill**，当前实测约 4000 token，这是上限：任何扩展必须先删除等量内容。对比：旧协议仅正文就超过 4300 行。

## 流程：状态机

```text
clarifying ──spec 完成、阻塞假设关闭──▶ specified ──plan 完成──▶ executing
                                                                    │
                                                                    │全部任务有证据
                                                                    ▼
        done ◀──review pass + 记忆更新──── reviewing ──review fail──▶ 回 executing 或 clarifying
```

- 任何阶段可进入 `blocked`：在 spec frontmatter 记 `blocked_from`（原阶段）和 `resume_when`（恢复条件），解除后按 `blocked_from` 回原阶段。
- 任何阶段可进入终态 `cancelled`：在 spec 意图区块下记一行作废原因。
- 状态只存在 `spec.md` frontmatter 的 `status` 字段，这是唯一的状态存储。
- 当前版本假定串行：同一时刻只有一个非终态 loop。

**知识状态**不是独立结构，它就是三样东西的当前值：假设表的状态列、验收标准的勾选与证据、任务清单的勾选与证据。状态机推进条件只读这三样。

## 环节与产物对照

| 环节 | 产物（唯一） | 对应 skill |
|---|---|---|
| 意图分析 + 假设提取 + 风险评估 | `spec.md` | workloop-spec |
| 计划生成 | `plan.md` | workloop-plan |
| 执行循环 | `plan.md` 内追加证据 + git 提交 | workloop-execute |
| 决策验证 / 认知一致性校验 / 语义验证 | `review.md`（独立视角） | workloop-review |
| 错误记忆更新 | `.workloop/memory.md`（项目级） | workloop-memory |

意图、假设、风险是 `spec.md` 里的三个必填区块，不是三个独立环节——环节越多，Agent 越笨。

## 目录与 Git 协议

```text
<project_root>/
├── .workloop/
│   ├── memory.md                # 项目级错误记忆，全项目一份
│   └── loops/<loop-id>/
│       ├── spec.md              # clarifying 产物；status 唯一存储处
│       ├── plan.md              # specified 产物；executing 阶段追加证据
│       └── review.md            # reviewing 产物；由独立视角写入
└── <代码、测试、文档在项目原有位置>
```

- `loop-id` 格式：`wl-<YYYYMMDD>-<两位序号>`，序号 = 当日已有 loop 最大序号 +1（创建前先列目录），创建后不变。
- 创建 loop 时必须把当前提交写入 spec frontmatter 的 `base_commit`；推荐同时创建同名分支（分支名 = loop-id）。review 的 diff 范围固定为 `git diff <base_commit>..HEAD`。

## 阶段推进条件（唯一的 Gate）

| 转换 | 条件（全部可肉眼或命令检查） | 由谁执行 |
|---|---|---|
| clarifying → specified | spec.md 四区块齐全；每条验收标准有验证方式；影响范围或验收的假设全部 confirmed/rejected 且附证据 | 执行者 |
| specified → executing | plan.md 每个任务映射到至少一条验收标准，且写明验证命令或人工步骤；最大风险有任务覆盖 | 执行者 |
| executing → reviewing | 每个任务勾选且后面贴有真实证据（含日期或提交 hash）；工作已提交 | 执行者 |
| reviewing → done / 退回 | review.md 存在、有外部锚、结论为 pass（→ done，且 memory.md 已按规则更新）或 fail（→ 按 review 指定退回） | 执行者按 review 结论机械执行，不得偏离；有异议升级给人裁决，裁决前 fail 有效 |

Gate 检查的是产物内容本身，任何人读一遍就能裁决。跑通若干真实需求后，再把被证明值得强制的检查固化为插件（hooks + 校验脚本），顺序不可颠倒。
