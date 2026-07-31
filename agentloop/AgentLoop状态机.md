# AgentLoop 状态机

## 目的

状态机只规定何时允许推进、退回、暂停和恢复。流程文档规定当前状态做什么；字段保存方式统一遵守[产物与目录协议](产物与目录协议.md)，所有转换遵守[AgentLoop 设计原则](AgentLoop设计原则.md)。

全局不变量：

- 必验集合来自需求、原型、契约等独立基线，不能由实现或测试自报名单反向定义。
- 每项义务必须能追溯到实现、契约、Gate、实际运行 Evidence 和恢复入口。
- Evidence 必须与 `loop_id + requirement_version + scope + flow/check + tested_commit` 精确匹配且当前有效。
- 状态表示已取得下一阶段许可，不表示产物天然正确；聚合时必须重新检查语义。
- 门禁默认关闭，但失败、重跑、completion 拒绝和旧产物升级都必须有可达的最小恢复路径。

## 普通 Loop 主状态

```text
draft
→ clarifying
→ awaiting_requirement_confirmation
→ ready_for_development
→ development_preparing
→ developing
→ ready_for_verification
→ verifying
→ verified
→ done
```

任一非终态可进入 `blocked` 或 `cancelled`。

`awaiting_requirement_confirmation` 是一个 Gate，不一定形成停顿：

- `manual`：必须等待有效人工确认事件。
- `auto_high_confidence`：满足项目策略时，可在同一执行循环中自动通过并记录自动判定依据。

Agent 不得把自己写入的字段冒充人工确认。

## 复合与 epic Loop 主状态

`execution_profile.level: composite` 在需求确认后使用。`loop_kind: delivery` 通过 `subflows` 聚合，`loop_kind: epic` 通过 `child_loops` 聚合：

```text
ready_for_development
→ orchestrating
→ verified
→ done
```

`orchestrating` 表示父状态由各子流程独立推进；主状态不再随着某一个子流程在开发和测试之间来回切换。

子流程状态：

```text
pending
→ development_preparing
→ developing
→ ready_for_verification
→ verifying
→ passed
```

失败状态为 `failed` 或 `blocked`；无需执行可标记 `skipped` 并记录原因。

## 执行单元聚合规则

```text
composite
→ 全部子流程为 passed 或有依据的 skipped
→ 每个产品 UI 子流程的原型页面、区域、交互、验收、automation 和 active visual evidence 覆盖完整
→ git.integration.status == verified
→ integration_verification.state 为 not_required 或 passed
→ 主状态 orchestrating → verified

epic
→ 全部必需子 Loop 为 done 或有依据的 skipped
→ 父 Loop 的 integration_verification.state 为 not_required 或 passed
→ 主状态 orchestrating → verified

全部子流程为 passed 或有依据的 skipped
或全部子 Loop 为 done/skipped
+ integration_verification.required == true
+ integration_verification 尚未 passed
→ 主状态保持 orchestrating
→ 推进 integration_verification

至少一个子流程可继续运行
→ 主状态保持 orchestrating

存在 failed
→ 主状态保持 orchestrating
→ 修复、退回或人工决定；不得进入 verified

所有未完成子流程均为 blocked
→ 主状态 blocked，resume_state: orchestrating
```

子流程可以开发与测试交错进行。例如 A 正在 `verifying`、B 正在 `developing`，主状态仍为 `orchestrating`。测试交接记录在各自的 `subflows[].verification_handoff`，不使用一份全局交接覆盖所有子流程。

同仓库 epic 必须先形成包含全部必需子交付的父集成提交，再在该提交上验证。跨仓库 epic 不要求一个 Git 集成提交，但 `integration_verification.handoff` 必须锁定每个子 Loop 的已验证交付提交和测试环境。

## 状态职责和出口

每个非终态必须同时定义五项契约：进入条件、允许工作、出口证据、失败去向、恢复重检。缺少任一项时不得新增或推进该状态。

| 状态 | 含义 | 主要负责人 | 出口条件 |
|---|---|---|---|
| `draft` | 已记录原始需求并完成初步复杂度分流 | 需求 Agent | 原始问题、背景及 `provisional` 执行档位已记录 |
| `clarifying` | 核对事实、目标、范围、验收和原型 | 需求 Agent | 分类义务集合、稳定验收 ID、独立来源、可观察结果和执行档位资格完整 |
| `awaiting_requirement_confirmation` | 执行需求确认 Gate | 需求负责人或审批策略 | 有效人工事件，或自动确认条件全部满足 |
| `ready_for_development` | 需求已确认，选择开发流程；复合/epic 在此完成总体编码前准备 | 开发 Agent 与协调者 | Git 基线、路由和“验收义务→实现→契约→验证”映射可用 |
| `development_preparing` | 调查现有实现并完成编码前产物 | 开发 Agent | 通用 assurance 或原型专用闭环通过；接口、数据及旧产物迁移路径按需完整 |
| `developing` | 编码、构建、静态检查和必要单元测试 | 开发 Agent | 开发自检完成；按验证策略直接验收或形成测试交接 |
| `ready_for_verification` | 开发交付等待测试接收 | 测试 Agent | 验证身份、tested commit、独立基线、执行器和入口检查完成 |
| `verifying` | 执行流程验证 | 测试 Agent | 从独立基线重算的必验集合全部被当前身份的 active Evidence 覆盖 |
| `orchestrating` | 调度、集成验证并聚合多个子流程或子 Loop | Loop 协调者 | 重新检查子单元语义、提交和 Evidence 后满足聚合规则，不能只信任 passed/done |
| `verified` | 必需验证已通过 | 完成策略 | 完成 Gate 通过 |
| `done` | 本轮开发 AgentLoop 完成 | 无 | 终态 |
| `blocked` | 暂时无法继续 | 当前负责人 | 阻塞解除并重新检查 `resume_state` |
| `cancelled` | 任务被明确取消 | 授权者 | 终态 |

`draft`、`clarifying` 允许分类和执行档位保持待确认；完整性门禁位于 `clarifying → awaiting_requirement_confirmation`。澄清前进入 `blocked/cancelled` 的 Loop 保留当时事实，不得使仓库级校验阻断其他 Loop。

## 正常转换

| 当前状态 | 目标状态 | 必需证据 |
|---|---|---|
| `draft` | `clarifying` | 原始需求和 `provisional` 执行档位 |
| `clarifying` | `awaiting_requirement_confirmation` | control v2 分类义务和验收义务完整；每条验收有稳定 `acceptance_id`、独立来源和可观察结果；必要原型、一致性检查和 `confirmed` 执行档位 |
| `awaiting_requirement_confirmation` | `ready_for_development` | 有效审批事件或自动确认依据 |
| `ready_for_development` | `development_preparing` | Git 基线、开发路由和验收义务映射 |
| `ready_for_development` | `orchestrating` | 总体控制闭环、切片/子 Loop、依赖、范围、Git 集成路线及 integration_verification 决定已检查 |
| `development_preparing` | `developing` | 编码前控制闭环完整；产品原型矩阵、接口与数据承载及迁移路径按需通过 |
| `developing` | `ready_for_verification` | 交付提交、开发自检、独立基线引用和精确验证身份；技术研究可交付实验脚本、原始结果和决策记录 |
| `developing` | `verified` | `routing.verification.policy == self_check` 且实际结果满足全部验收 |
| `ready_for_verification` | `verifying` | 测试范围、复用流程、执行器、精确验证身份和 tested commit |
| `verifying` | `verified` | 每个必需 `acceptance_id` 的实现及 flow/check 映射完整，并由当前 tested commit 上身份匹配的 active passed Evidence 全量覆盖；各独立 Gate 均通过 |
| `orchestrating` | `verified` | composite 或 epic 的义务、提交、Evidence 身份与生命周期及各独立 Gate 重新聚合后全部满足 |
| `verified` | `done` | 完成 Gate 通过 |

`trivial` 模式仍保存这些逻辑状态，但允许在一次执行循环内连续通过多个已满足的 Gate。选择 `self_check` 时不进入独立测试状态，直接由 `developing → verified`，但必须保存真实检查结果。项目只有同时显式启用自动需求确认和自动完成时，trivial 才能无人工停顿地单轮完成。

## Loop 编排职责

每个非终态 Loop 必须有一个 `owners.coordination`。Loop 协调者负责：

- 决定当前推进哪个状态、子流程或子 Loop
- 获取锁、检查范围冲突、交接任务并聚合状态
- 保证角色权限、需求版本、Git 和证据一致
- 在 Gate、低置信度和阻塞处停止

协调者没有需求确认权或测试通过权，除非它同时被明确授予对应角色。同一个 Agent 可以顺序切换多个角色，但每次操作必须以实际角色记录 `actor`；多个 Agent 协作时只有协调者更新主状态，当前负责人更新自己的产物后交接。

`self_check` 是明确例外：它不产生“测试 Agent 已通过”的结论。开发 Agent 记录直接验收结果后，协调者只依据已确认的 `self_check` 策略推进 `developing → verified`，不冒充测试角色。

路由只允许在 `ready_for_development` 或 `development_preparing` 更新。进入 `developing` 后发现路由错误，必须先退回 `development_preparing`；不得原地改成 trivial/self_check 或降低验证策略。

## 子流程受控状态转换

Composite 父 Loop 进入 `orchestrating` 只表示协调开始，不授予任何子流程编码许可。子流程必须通过 `transition --subflow-id` 逐步推进；该命令实际修改对应子流程并执行其门禁。`development_preparing → developing` 对产品原型子流程强制检查实现矩阵、用户流程切片、OpenAPI 契约、服务端承载和验证方案；`verifying → passed` 强制检查视觉与业务功能证据。

直接编辑 `loop.yaml.state`、`subflows[].state`、Gate 状态或 `evidence.validity` 属于非法旁路。控制程序比较受控字段快照，发现差异时恢复最后合法值并拒绝当前操作。

## Git 基线门禁

第一次修改项目文件前必须满足：

```text
项目由有效 Git 仓库管理
+ baseline_commit 已保存
+ 工作区已有变化已经识别
+ 用户已有修改不会被覆盖
```

项目不是 Git 仓库时，必须先按[Git 版本控制与可追溯规则](../rules/Git版本控制与可追溯规则.md)检查提交范围，通过 `repository_bootstrap` Gate，再完成初始化和初始基线提交。无法建立安全基线时进入 `blocked`。

## 失败与退回

```text
需求缺失、冲突或验收不可执行
→ clarifying

开发准备或编码中发现主流程、子流程或设计路线选错
→ development_preparing
→ 更新路由和编码前产物后重新进入 developing

开发中发现 execution_profile 低估复杂度，但需求范围和验收未变
→ development_preparing
→ 只允许 trivial → standard → composite 升级
→ 迁移规范文件并更新路由
→ trivial 升级后原 self_check 失效，必须重新选择 targeted 或 flow

execution_profile 变化同时改变范围或验收
→ clarifying
→ requirement_version 加一并重新确认

设计改变范围、核心流程或验收标准
→ clarifying
→ 需求版本加一并重新确认

开发自检失败
→ 保持 developing

测试发现实现错误
→ developing
→ 修复后重新形成 ready_for_verification

测试发现测试代码、环境或数据错误
→ 保持 verifying

测试发现需求或预期错误
→ clarifying

集成验证发现切片组合错误
→ 标记 integration_verification: failed
→ 按证据将受影响子流程退回 developing
→ 无法归属时 blocked，交由协调者拆解

切片合并冲突或合并后定向检查失败
→ git.integration 标记 conflict 或保留未验证状态
→ 受影响子流程从 passed 退回 developing
→ 重新产生并验证 source_commit 后再合并
```

复合 Loop 对当前子流程执行同样退回，父状态保持 `orchestrating`；只有整体需求改变时，父状态退回 `clarifying`。

completion Gate 反馈“与原型不一致”且需求预期未改变时，不增加需求版本：

```text
按受影响 prototype_path/route 定位页面和产品 UI 子流程
→ 相关 active UI evidence 标记 stale
→ 相关子流程退回 development_preparing；普通 Loop 主状态退回 development_preparing
→ composite/epic 父 Loop 回到或保持 orchestrating
→ failure_handoff 保存失败证据、影响页面和重新验证范围
```

未受影响子流程和证据保持原状态；受影响页面无法映射到实现矩阵时恢复操作失败并进入人工定位，禁止全量无差别重做。

从测试退回时必须保存失败证据、问题归属和重跑范围。开发与测试往返次数遵守执行协议的全局熔断规则。

## 需求变更与失效

`ready_for_development` 之后需求变化：

```text
退回 clarifying
→ requirement_version 加一
→ 重新确认范围和验收
→ 将受影响 artifact/evidence 标为 stale
→ 将被替代产物标为 superseded
→ 未受影响产物保持 active
→ 重新选择或确认开发与测试路由
```

旧需求版本对应的提交、产物和证据不得删除；具体字段见产物协议。

## Gate 事件

人工 Gate 只接受宿主系统、UI、CLI 或 API 记录的有效事件。策略 Gate 由宿主策略引擎记录。两者都必须绑定：

```text
loop_id
+ gate_id
+ requirement_version
+ 待确认产物摘要 artifact_digest
+ decision
+ actor
+ timestamp
+ source_event_id
```

用户在对话中回复“可以”只有在宿主将该消息记录为上述审批事件时才算确认。Agent 只能引用事件，不能代填 `actor` 或伪造 `source_event_id`。

策略事件使用 `source: agent-policy`，仍必须由宿主分配唯一 `source_event_id`。自动需求确认只在项目配置为 `auto_high_confidence`，且同时满足以下条件时允许：

```text
execution_profile.level == trivial
+ gates.requirement_confirmation.confidence >= minimum_confidence
+ classification.tags 不包含 forbidden_tags
+ trivial 资格条件全部满足
+ 无未解决问题
```

delivery 子 Loop 可以使用 `inherited_from_parent` 自动通过需求确认 Gate，但必须同时满足：

```text
父 Loop 的 gates.requirement_confirmation.status == approved，且 Gate 事件绑定当前 requirement_version
+ 子 Loop scope 是父确认范围的真子集或相等
+ 子验收标准只是父验收标准的拆分，没有新增预期
+ 没有新增业务规则、约束、风险标签或外部依赖
+ parent approval event 和 artifact_digest 可定位
+ scope_subset_check、acceptance_subset_check 均 passed
```

继承由 Loop 协调者写入引用和检查结果，不能伪造新的人工确认事件。任一条件不满足时，子 Loop 正常进入人工或 `auto_high_confidence` Gate。父需求版本变化会使所有继承确认失效：非终态子 Loop 退回 `clarifying`；已 `done` 的子 Loop 不重开，受影响产物标记 `stale` 并创建后继子 Loop。

破坏性操作始终人工确认。

## 阻塞与恢复

进入 `blocked` 时使用产物协议中的：

```yaml
blocked:
  reason:
  owner:
  unblock_condition:
  resume_state:
```

解除后只回到 `resume_state`，并重新检查该状态入口。每次转换追加 `transitions`；字段以产物协议为准，不再维护 `active_flow`、`active_subflow`、`owner` 等重复字段：

- 当前开发主流程：`routing.development.main_flow`
- 当前执行子流程：`execution.subflow_id`
- 角色负责人：`owners`

## 完成条件

```text
所有必需验证通过
+ 当前执行结构满足对应条件：
    standard → 无未完成执行单元
    composite → 子流程为 passed/skipped，且代码已形成 verified integration commit
    epic → 必需子 Loop 为 done 或有依据的 skipped；同仓库父集成提交已验证，或跨仓库交付提交集合已锁定
+ 必需集成验证通过
+ 当前验证策略要求的产物、自检记录和证据有效
+ completion Gate 通过
+ Git 检查点可查询
+ 无未处理阻塞
→ done
```

`done` 只表示本开发 AgentLoop 完成，不代表已经发布到生产。
