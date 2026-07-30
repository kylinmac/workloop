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
