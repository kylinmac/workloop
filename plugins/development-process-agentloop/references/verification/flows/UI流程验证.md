# UI 流程验证

## 适用范围

需要通过真实页面点击、输入、跳转和用户可见结果判断的流程。

## 执行流程

```text
根据测试交接确定需要验证的用户流程
→ 按覆盖索引查找已有可复用测试流程定义和浏览器自动化
    ├── 已存在
    │   → 确认预期保持不变还是按需求改变
    │   → 复用原点击脚本；只更新明确改变的断言
    └── 不存在
        → 写点击步骤和预期
        → 编写浏览器自动化
→ 准备账号和数据
→ 真实打开页面
→ 点击、输入并等待
→ Assert 页面状态
→ 在关键步骤截图
→ 保存报告和失败录像
→ 通过，或修复后重跑
```

## 产物规则

```text
已有用户流程回归
→ 复用原测试流程定义和 UI 自动化
→ 只新增本次报告、截图和失败证据

新增独立用户流程
→ 新增测试流程定义、UI 自动化和运行证据
```

### `.agentloop/flows/<flow_id>.yaml`

只有没有现有用户流程可以覆盖时才新增。定义必须包含 `covers` 的页面路由、路径和标签。需求明确改变交互时，在原定义中更新受影响步骤和预期。

```yaml
flow_id: refund-ui
executor: ui
steps:
  - action: 打开订单详情
    expect: 显示申请退款按钮
    screenshot: 01-order-detail
  - action: 点击申请退款并提交
    expect: 显示退款审核中
    screenshot: 02-refund-submitted
checks: [visual, interaction, state]
```

当 `checks` 包含 `visual`，或原型类型为 `high_fidelity` 时，flow 还必须包含：

```yaml
automation:
  path: tests/ui/dashboard-prototype.spec.ts
prototype:
  type: high_fidelity
  references:
    - prototype_path: design/01-dashboard.html
      route: /dashboard
visual_validation:
  viewport: {width: 1440, height: 900}
  comparison: both               # dom | screenshot | both
  allowed_differences: [运行时时间文本]
  pass_criteria: DOM 必需项全量匹配，排除允许差异后截图差异不超过 1%
coverage:
  - prototype_path: design/01-dashboard.html
    route: /dashboard
    region_id: summary
    interaction_id: open-detail
    acceptance_id: AC-UI-01
    automation_steps: [dashboard-open-detail]
```

每个视觉步骤必须有稳定 `step_id` 和截图名。参考原型、固定视口、DOM/结构或截图对比、允许差异、通过标准缺一不可；每个范围内页面至少有一组参考与实现证据。只断言页面打开、页面可见、API 返回或少数点击，不能替代原型保真验证。

### UI 自动化文件

一个测试文件对应一个用户流程。已有文件能够覆盖时直接复用。测试必须真实操作控件并 Assert：

- 页面内容
- 控件状态
- 表单校验
- 跳转和反馈
- 加载、空、错误和无权限状态

前置数据可通过 API 或夹具准备，不要求全部通过 UI 创建。

`automation.path` 必须指向项目内真实存在的测试或脚本文件。`.md` 只能作为报告写入 evidence 的 `stdout_path` 或 artifact，禁止作为 automation。控制程序同时检查路径未逃逸项目根、文件存在，并具有脚本/测试扩展名或可执行权限。

### 数据库到页面的真实数据验证

`integration_data.required: true` 时，前置数据必须由自动化通过 seed、factory 或 fixture 写入隔离测试数据库，不得用前端 mock、路由拦截或写死响应替代。flow 的 `checks` 必须包含 `data_lineage`，随后调用真实后端接口并操作真实页面，逐层断言同一个本次运行唯一 sentinel。

运行证据使用 `data_lineage` 保存数据库对象、后端接口、前端路由的覆盖和各层观察值。三层观察值不一致或未覆盖声明范围时，UI flow 不得通过。

### 产品原型业务功能 Gate

产品原型 UI 自动化必须由插件实际执行，并在 `AGENTLOOP_REPORT_PATH` 生成绑定 `AGENTLOOP_CODE_COMMIT` 的报告。调用方不得提交任意 coverage、visual、data lineage 或预写 passed JSON；插件在运行前删除旧报告，并从本次测试报告生成 evidence。

每个服务端 interaction 必须有真实浏览器操作及大于零的断言，覆盖 operation/响应、数据库或 Repository 持久化、readback、刷新、重登、失败、无权限、下游消费和审计。必需交互不得 skipped。Toast、关闭弹窗、页面跳转或 React 本地状态变化不能代替持久化证据。

视觉保真和业务功能是两个独立 Gate：截图/DOM 通过不能补偿业务失败；业务通过也不能跳过高保真视觉要求。

### 运行证据

- 测试框架报告
- 关键步骤截图
- 失败时的录像、控制台和网络错误
- 测试视口、账号角色和代码版本

原型验证的 evidence 必须逐行形成覆盖矩阵：

```text
原型页面 → 页面区域 → 关键交互 → 验收标准
→ flow automation step → evidence screenshot/artifact
```

`evidence.runs[].coverage` 保存逐行映射，`visual` 保存实际视口、对比方式、允许差异、通过标准，以及每页参考和实现文件。控制程序按 `prototype-implementation-matrix` 计算必需行集合；任一页面、区域、关键交互、验收 ID、自动化步骤或证据缺失时不得标记 passed。范围为 01–09 时只验证两页，缺少的七页会形成覆盖错误。

## 完成条件

核心点击路径能够真实跑通，关键页面状态有 Assert 和截图，失败能够通过报告或录像定位。触发原型保真门禁时，还必须满足原型页面集合、flow 覆盖和 active passed evidence 覆盖完全一致。
