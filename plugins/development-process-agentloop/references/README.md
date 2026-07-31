# AI 开发流程库

## 目的

本仓库用于沉淀 AgentLoop 可以选择和组合的流程，并提供可直接安装到 Codex 的执行插件。

根目录下的流程文档和 `agentloop/` 是唯一源码；`plugins/development-process-agentloop/` 提供轻量控制程序和发布快照。

## 流程层次

```text
需求产生
→ 初判 trivial / standard / composite
→ 执行可裁剪的需求确认流程
→ 确认复杂度档位
→ 需求达到可开发状态
→ 选择开发流程
→ 产生可交付实现
→ 选择 self_check / targeted / flow 验证策略
→ 形成验证结论
```

不同层次的流程保持独立。需求分类回答“是什么变化”；执行模式回答“需要多少产物和怎样调度”；开发主流程回答“编码前最需要消除什么不确定性”；测试执行器回答“怎样取得可信结果”。

简单需求可合并阶段、按策略自动通过 Gate，并以真实自检直接验收；复杂需求由子流程或父子 Loop 独立开发验证，最后通过跨切片集成验证聚合。

## 目录导航

### 通用规则

- [通用流程定义规则](rules/通用流程定义规则.md)
- [Git 版本控制与可追溯规则](rules/Git版本控制与可追溯规则.md)

### 需求阶段

- [需求分类](requirements/需求分类.md)
- [需求阶段总览](requirements/需求阶段总流程.md)
- [需求确认流程](requirements/flows/需求确认流程.md)

### 开发阶段

- [开发流程定义规则](development/开发流程定义规则.md)
- [开发流程体系总览](development/开发流程体系总览.md)
- [快速变更流程](development/flows/快速变更流程.md)
- [产品原型驱动流程](development/flows/产品原型驱动流程.md)
- [业务流程驱动流程](development/flows/业务流程驱动流程.md)
- [数据与契约驱动流程](development/flows/数据与契约驱动流程.md)
- [领域模型驱动流程](development/flows/领域模型驱动流程.md)
- [架构驱动流程](development/flows/架构驱动流程.md)
- [根因驱动修复流程](development/flows/根因驱动修复流程.md)
- [迁移与兼容驱动流程](development/flows/迁移与兼容驱动流程.md)
- [技术验证驱动流程](development/flows/技术验证驱动流程.md)

### 测试验证阶段

- [测试验证流程定义规则](verification/测试验证流程定义规则.md)
- [测试验证流程体系总览](verification/测试验证流程体系总览.md)
- [代码流程验证](verification/flows/代码流程验证.md)
- [UI 流程验证](verification/flows/UI流程验证.md)
- [命令与实验流程验证](verification/flows/命令与实验流程验证.md)

### AgentLoop 控制层

- [AgentLoop 设计原则](agentloop/AgentLoop设计原则.md)
- [AgentLoop 状态机](agentloop/AgentLoop状态机.md)
- [AgentLoop 产物与目录协议](agentloop/产物与目录协议.md)
- [AgentLoop 路由与阶段交接协议](agentloop/路由与阶段交接协议.md)
- [AgentLoop 执行、重试与恢复协议](agentloop/执行重试与恢复协议.md)
- [AgentLoop JSON Schema](agentloop/schemas/)
- [AgentLoop 最小有效样例](agentloop/examples/)

### Codex 插件

- 插件源码位于 [`plugins/development-process-agentloop/`](plugins/development-process-agentloop/)。
- `requirements/`、`development/`、`verification/`、`rules/`、`agentloop/` 和本 README 是流程知识的唯一源码。
- 插件的 `references/` 是生成的发布快照，不应直接修改。
- 修改流程源码后执行 `python3 plugins/development-process-agentloop/scripts/sync_references.py sync`；提交前执行同一脚本的 `check` 命令检查漂移。

## 当前边界

当前流程库已经完成：

- 需求分类、需求阶段总览和通用需求确认流程
- 通用流程定义规则
- Git 版本控制与可追溯规则
- 开发流程定义规则
- 测试验证流程定义规则
- 九类开发流程
- 测试验证流程分类总览
- 三类可执行测试验证流程
- AgentLoop 统一状态机
- AgentLoop 设计原则与控制闭环
- AgentLoop 产物与目录协议
- AgentLoop 路由与阶段交接协议
- AgentLoop 执行、重试与恢复协议
- 可配置需求、路由、完成和破坏性操作 Gate
- trivial 快车道、复合子流程聚合和父子 Loop 拆分
- self_check / targeted / flow 三档验证策略
- Loop 协调者职责、切片集成分支合并/复验与跨切片集成验证
- 父需求确认继承、子 Loop 状态单一来源和分层验证往返熔断
- 多 Loop worktree/范围冲突约束和产物失效标记
- project/loop/flow/evidence 四类 JSON Schema 与 trivial/standard/composite/epic 样例

## V1 边界

- 当前 V1 覆盖需求确认、开发、开发自检、测试验证，以及按策略进行的人工或自动 Gate。
- 发布、生产运行和用户反馈属于后续独立流程，不包含在本开发 AgentLoop 中。
- 特殊需求确认流程只在通用流程确实无法覆盖时增加。
- Codex 插件提供基于 Python 的轻量控制程序；协议本身仍不绑定业务项目的技术栈。
