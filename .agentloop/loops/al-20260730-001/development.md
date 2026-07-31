# 开发记录

## 输入与需求版本

`requirement_version: 1`；事故输入与八项机器门禁验收见 `requirement.md`。

## 主开发流程及依据

`root-cause`。验证入口、flow、evidence、subflow 聚合和 completion Gate 恢复均汇聚在 `scripts/agentloop.py`，应在共享语义校验处一次修复。

## 现有系统调查

当前 `cmd_validate` 只逐文件执行 JSON Schema；`active_passed_evidence` 只要求任意一条当前版本 passed；`aggregation_errors` 只检查子状态和集成状态；`flow.schema.json` 允许任意 `automation.path`；completion Gate 拒绝只写 Gate 状态，不失效证据或回退 UI 单元。协议虽然要求 UI 点击和截图，但没有可供控制程序检查的结构化原型/覆盖字段。

## 编码前产物及检查

修复点：

1. 在 `loop.yaml` 结构化声明原型类型、四维保真要求、逐页路由/验收和允许偏差。
2. 新增 `prototype-matrix.schema.json`，并由 `files.prototype_matrix` 引用逐页实现矩阵。
3. 扩展 UI flow 的 visual contract、coverage entries 和 automation 路径约束。
4. 扩展 evidence 的逐项 coverage 与 visual result。
5. 在控制程序增加跨文件语义检查，复用于 `validate`、状态转换和父级聚合。
6. completion Gate 原型不一致拒绝时按矩阵页面归属定向回退并失效相关 UI evidence。

不变行为：未声明原型依据、未选择 `product-prototype` 且不含 visual check 的旧 Loop 继续按原策略校验；非 UI flow 不强制视觉字段。

回归设计：新增三个高保真 HTML 原型的失败 fixture，只有一个页面打开步骤且 automation 指向 Markdown，断言 `validate` 和 `verifying -> verified` 均失败；补充完整覆盖的通过 fixture。

## 子流程与依赖

单一 standard Loop，无子流程。
## 实现和修改文件

协议：

- `requirements/flows/需求确认流程.md`
- `development/flows/产品原型驱动流程.md`
- `verification/flows/UI流程验证.md`
- `agentloop/AgentLoop状态机.md`
- `agentloop/产物与目录协议.md`
- `agentloop/路由与阶段交接协议.md`
- `agentloop/执行重试与恢复协议.md`

结构与控制：

- `agentloop/schemas/loop.schema.json`
- `agentloop/schemas/flow.schema.json`
- `agentloop/schemas/evidence.schema.json`
- `agentloop/schemas/prototype-matrix.schema.json`
- `plugins/development-process-agentloop/scripts/agentloop.py`

示例与回归：

- `agentloop/examples/prototype-matrix.yaml`
- `agentloop/examples/ui-visual.flow.yaml`
- `agentloop/examples/ui-visual.evidence.yaml`
- `agentloop/validate_examples.py`
- `plugins/development-process-agentloop/scripts/test_prototype_fidelity.py`
- `plugins/development-process-agentloop/scripts/test_agentloop.py`

## 开发自检

通过：

```text
python3 agentloop/validate_examples.py
python3 plugins/development-process-agentloop/scripts/sync_references.py check
python3 plugins/development-process-agentloop/scripts/test_agentloop.py
python3 <installed-plugin>/scripts/agentloop.py doctor
python3 <installed-plugin>/scripts/test_agentloop.py
git diff --check
```

事故样例验证了四个阻断点：实现矩阵缺页不能进入 `developing`；三页只覆盖一页且 automation 指向 Markdown 时 `validate` 失败；父聚合不能只信任 `subflow.state: passed`；`verifying → verified` 失败。补齐三页 flow、automation、截图/证据后才能进入 `verified`。completion Gate 原型不一致拒绝后，相关 UI evidence 变为 stale，Loop 定向回到 `development_preparing`。

## 测试交接

复验命令：`python3 plugins/development-process-agentloop/scripts/test_agentloop.py`。该命令包含完整插件生命周期和原型保真事故回归。

## 需求版本 2：前后端真实数据链路

适用边界仅为需要前后端对接、且业务数据按设计应从数据库读取的功能。编码前在 `loop.yaml` 明确 `integration_data.required`；启用时登记前端路由、后端接口、数据库对象和验证 flow。

机器门禁复用现有 flow/evidence/状态转换入口：

1. flow 必须包含 `data_lineage` 检查并指向可执行自动化。
2. 测试通过 seed、factory 或 fixture 向隔离数据库写入唯一 sentinel。
3. evidence 必须证明数据库、后端 API、前端页面观察到同一 sentinel，并覆盖声明的全部路由、接口和数据库对象。
4. 缺失、覆盖不全或 sentinel 不一致时，`verifying -> verified` 和父级聚合均失败。

静态界面文案、枚举和纯展示配置不属于业务数据，不触发该门禁。

## 需求版本 3：实现方案

在共享控制入口一次完成四项修复：扩展 prototype matrix 并解析 OpenAPI operation；将视觉与业务功能证据独立校验；让 evidence 命令实际运行测试并读取新生成的 commit-bound 报告；实现 `transition --subflow-id` 和受控字段快照恢复。新增一个生产预算系统回归，覆盖契约缺失失败、完整持久化旅程通过、直接状态篡改被恢复及子流程命令真实推进。

## 需求版本 4：实现方案

新增统一 `tested_commit_for_scope`：子流程从 transition 历史逆序取自身最近一次 `to: verifying` 的 `git_commit`；顶层验证继续取 integration delivery/head。回归覆盖旧父级 commit、其他子流程 transition、多轮重验和缺失 verifying transition。

## 需求版本 5：实现方案

增加 `integration-checkpoint` 控制命令：只使用当前 HEAD，并校验所引用 Evidence 均为当前需求版本、当前提交、active/passed；原子更新集成 head、delivery、checkpoint 与集成验证 handoff。父级原型验证复用同一 scope 过滤，聚合 passed 子流程在当前集成提交上的视觉覆盖和业务旅程，子流程自身验证规则保持不变。

## 需求版本 6：实现方案

新增 `prototype-behavior-inventory` Schema 与受控扫描命令，清单绑定原型文件 SHA-256，并把点击监听器、表单提交和导航目标作为独立候选。扩展 prototype matrix 的行为来源映射、旅程责任和导航 outcomes；编码前对 inventory → matrix → user-flow 做差集检查。UI 报告新增 navigation coverage，控制程序要求 `user_action`、来源路由和每个必需 outcome，并拒绝直接导航作为功能证据。

新增 `agentloop/issues/`，每个缺陷一个文档，索引只负责导航。流程规则要求插件修复提交必须包含对应问题档案和回归命令。

## 需求版本 6 补充：设计原则与流程重构

新增唯一原则文档，避免在各流程重复定义同一控制语义；需求阶段建立独立验收义务，开发阶段建立义务到实现/契约/验证的映射，测试阶段独立重算集合并按精确身份消费 Evidence。状态机补齐五项契约，交接和恢复协议补齐证据替代、最小失效、旧产物迁移及五路径回归。控制程序只增加一项必要检查：doctor 必须确认设计原则已进入插件发布快照。

## 需求版本 7：实现方案

使用两个共享契约修复文档层缺口：`classification.obligations` 负责需求类型义务，`development-assurance.yaml` 负责路线义务到来源、产物、检查、Gate 和恢复的映射。各路线只声明必需 obligation ID，不复制 Schema。

控制层在共享入口修复：快照 v2 覆盖 Evidence 核心字段且缺失失败；Gate 消费时复算 subject；人工批准支持宿主 HMAC 认证并限制状态；flow Evidence 统一要求 nonce/commit/断言报告；增加 `repair-control` 和 `runtime-upgrade`。回归覆盖伪造批准、摘要变化、快照删除、Evidence 篡改、assurance 缺项、result 冲突、非 UI flow 无报告和 Schema 漂移。
