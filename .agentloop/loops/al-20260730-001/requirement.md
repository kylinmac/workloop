# 阻止高保真原型实现失真通过验证

## 原始需求与事实

已有高保真 HTML 原型被声明为实现依据，但原型信息、逐页实现矩阵、视觉验证契约和证据覆盖均未形成机器门禁。现有控制程序只要发现当前需求版本存在一条 passed evidence，或复合子流程状态为 passed，便允许聚合；它不检查 UI flow 的 automation 文件类型、原型页面覆盖或视觉证据完整性。

## 用户、场景与目标

插件使用者依据多个原型页面实现产品 UI 时，AgentLoop 必须在编码前、子流程通过、父级聚合和最终验证四个位置自动检查原型保真与证据覆盖，不能把问题推迟到 completion Gate。

## 范围、非目标、规则与约束

范围：需求确认协议、产品原型驱动协议、UI 验证协议、状态恢复协议、JSON Schema、控制脚本、示例和插件级回归测试。

非目标：实现具体项目的截图比较器；插件只要求并校验项目提供的可执行自动化、固定视口、对比契约和逐项证据。

兼容约束：旧 Loop 未声明原型实现依据且未选择 `product-prototype` 时保持可用；新增严格门禁只在原型或视觉条件触发。

## 验收标准

1. 声明原型为实现依据但缺少类型、四维保真策略、逐页路由/验收或允许偏差时，`validate` 或需求阶段转换失败。
2. `product-prototype` 在缺少完整 `prototype-implementation-matrix.yaml` 时不能进入 `developing`。
3. UI flow 包含 `visual` 或高保真原型时，缺少参考路径、固定视口、结构/截图对比、通过标准、逐页逐区域交互覆盖时校验失败。
4. `automation.path` 为 Markdown、不存在或不是脚本/测试文件时运行态校验失败。
5. 三个高保真原型只覆盖一个、仅检查页面打开且 automation 指向 Markdown 的事故样例不能进入 `verified`。
6. composite/epic 聚合除状态外还检查原型覆盖、有效视觉证据、可执行 automation 和验收到证据映射。
7. completion Gate 以“与原型不一致”拒绝时，仅失效相关 UI 证据，相关 UI 子流程回退，父 Loop 回到 `orchestrating`，并保留影响页面与重验范围。
8. 完整覆盖的通过样例、Schema 示例、插件生命周期测试和可重复回归命令全部通过。

## 分类与复杂度

内部改进；standard。主不确定性是现有控制程序的跨文件语义校验边界，采用根因驱动修复，验证策略为 targeted。

## 需求原型决定与引用

本次修改不实现产品页面，无需求原型。事故中的原型用于构造失败回归样例。

## 未解决问题

无。

## 确认记录

用户在当前请求中明确给出事故、八项修改范围和机器门禁验收重点。

## 需求版本 2：前后端联调数据来源约束

### 原始需求与边界

对于需要前后端对接的功能：

- 前端页面展示的业务数据不得写死在页面、组件、状态初始化或 fallback 中，必须来自后端接口。
- 后端字段按业务设计应从数据库读取时，不得在 Controller、Service、Repository 外围或接口响应中写死，必须真实查询数据库。
- 联调和验收测试先通过 seed/factory/fixture 向隔离测试数据库生成带唯一标识的数据，再调用后端接口，最后由前端页面查询并展示同一标识的数据。
- 静态界面文案、枚举定义、展示配置和不属于业务记录的数据不在此限制内；不得以“fallback”“demo”“临时 mock”名义绕过运行时数据链路。

### 验收标准

1. 新 Loop 必须明确 `integration_data.required`；需要前后端联调时必须填写前端路由、后端接口、数据库对象和验证 flow。
2. 缺少上述声明时不得进入开发。
3. 验证 flow 必须是可执行脚本，并包含 `data_lineage` 检查。
4. evidence 必须使用同一随机 sentinel 证明“测试数据库生成 → 后端接口查询返回 → 前端页面展示”的完整链路。
5. 数据库对象、接口或前端路由任一未覆盖，或三段 sentinel 不一致时不得进入 `verified`，父级聚合也不得通过。
6. 不需要前后端对接的任务可记录 `required: false` 和理由，保持兼容。

### 复杂度与原型

仍为 standard 内部改进；本次不需要产品原型。新增范围采用根因驱动修复和 targeted 验证。

### 确认记录

用户澄清该规则只针对需要前后端对接的代码，并明确数据库生成、后端查询返回、前端查询展示的测试链路。

## 需求版本 3：产品原型业务完成与控制可信门禁

高保真原型只作为生产系统 UI 实现依据，视觉复刻不能替代业务功能验收。`product-prototype` 的每个可操作 interaction 必须在编码前绑定真实 OpenAPI operation，并声明数据库前置状态、用户操作、mutation 响应、持久化变化、readback、刷新/重登结果、失败和无权限场景。纯静态页面或复用接口只能通过显式豁免/复用声明跳过新契约。

写操作必须由真实浏览器自动化执行，并证明 API、数据库或 Repository、刷新、重登和后续流程消费结果。Toast、弹窗关闭、跳转或前端本地状态变化不能单独通过。所有业务记录和指标必须能追溯到 seed/factory、数据库、正式 API 字段或服务端计算口径；无数据时显示空态。

Evidence 不接受调用方自报 `passed`、任意 coverage JSON 或预写 interaction JSON。插件必须实际执行测试命令或解析受支持测试报告，验证断言数大于零、必需交互未跳过、报告和当前提交一致，并由执行结果生成 evidence/coverage。

Composite 子流程只能由 `transition --subflow-id` 改变状态；进入 `developing` 必须执行该子流程的原型矩阵、用户旅程切片、接口契约、数据承载和验证方案门禁。主 Loop 进入 `orchestrating` 不等于子流程获准编码。

控制程序必须维护受控字段摘要，检测 `state`、子流程状态、Gate 状态和 evidence validity 的旁路修改。检测到篡改时拒绝推进并恢复最后合法控制状态。

最终 `verified` 前必须至少有一条完整用户旅程证据：创建 → 编辑 → 保存 → 刷新 → 重新登录 → 查询 → 后续流程消费 → 审计可追溯。视觉 Gate 与业务功能 Gate 独立，任一正式 API 缺失、写操作未持久化或必需业务交互失败都必须阻止通过。

## 需求版本 4：修复子流程 Evidence 提交绑定

Composite 子流程验证时，业务 Evidence 的 tested commit 必须取该子流程最近一次合法进入 `verifying` 的 transition `git_commit`，不得使用父 Loop 旧的 `git.integration.delivery_commit/head_commit`。父流程或集成级验证仍使用精确的 integration delivery/head commit。

验收标准：

1. 子流程最近一次 `to: verifying` transition 为 `46804e8` 时，绑定同一 commit 的真实 UI report 可以通过，即使父级 integration commit 仍为旧值。
2. Evidence 与子流程 verifying transition commit 不一致时仍必须失败。
3. 多轮重验时取同一子流程最后一次进入 `verifying` 的 commit，不受其他子流程 transition 影响。
4. 父级验证的提交选择保持原行为。

## 需求版本 5：集成 checkpoint 与父级 Evidence 聚合

Composite/epic 必须能通过控制命令把当前 Git HEAD 原子记录为集成 head/delivery checkpoint；调用方不得直接编辑 `loop.yaml`。命令只接受当前需求版本、当前提交上真实执行且 active/passed 的 Evidence，并同步集成验证 handoff。

复合父流程的原型视觉与业务完成门禁必须聚合已通过子流程的 Evidence，而不是要求重复生成 `subflow_id: null` 的父级 UI Evidence。聚合只接受当前需求版本、当前集成提交、active/passed 且属于已通过子流程的 Evidence。

验收标准：

1. 合法 checkpoint 将 `git.integration.head_commit`、`delivery_commit` 和验证 handoff 绑定当前 HEAD。
2. 旧提交、旧需求版本、失败、stale 或未知 Evidence 必须被 checkpoint 拒绝。
3. `sf-04-product-ui` 的当前提交 UI Evidence 能覆盖父级 48 条视觉/业务矩阵和完整生产旅程。
4. 父级聚合不得跨需求版本、跨集成提交或聚合未通过子流程的 Evidence。

## 需求版本 6：原型行为独立清单与问题档案

原型实现矩阵不能继续自行定义“完整交互集合”。高保真或交互原型在编码前必须存在与原型源文件摘要绑定的独立行为清单，记录机器扫描发现的点击/提交/导航候选和分支结果。矩阵必须逐项映射行为清单；未映射、重复映射、源文件摘要失效或存在未解决候选时，禁止进入 `developing`。

状态驱动导航必须显式声明来源页面、用户触发动作、是否允许直接进入，以及每个条件分支的预期界面或目标路由。用户旅程必须覆盖所有 `journey_required` interaction 及其必需 outcome，不能只覆盖服务端写操作。

UI Evidence 对导航交互必须证明从来源页面执行真实用户动作并观察到目标结果。直接访问目标 URL 只能作为视觉截图入口，不得满足 interaction/outcome coverage。Evidence 缺少动作类型、来源路由、结果路由或覆盖分支时必须失败。

插件仓库建立问题档案目录。每次插件缺陷修复至少新增或更新一个独立问题文档，记录现象、影响、根因、为何旧 Gate 未拦截、修复、回归和预防规则；历史已知问题按一问题一文档补齐。

验收标准：

1. 原型包含状态分支导航但行为清单或矩阵漏项时，编码前 Gate 失败。
2. 矩阵声明导航但用户旅程漏掉必需 outcome 时，编码前 Gate 失败。
3. UI 自动化直接 `goto` 目标页且没有来源页面点击证据时，Evidence/verified Gate 失败。
4. 从需求列表点击不同状态记录并到达对应页面时，通过导航交互 Gate。
5. 插件历史问题形成独立文档，并在流程中强制后续修复持续记录。
