# 阶段 2：固化机器契约

- 状态：completed
- 阶段目标：用机器 Schema 固化 project、loop、flow、evidence 字段，并提供四档有效样例。
- 输入与约束：Schema 只表达已落地协议，不增加新流程；样例覆盖 trivial、standard、composite、同仓库 epic。

## 工作项
- [x] 增加四类 JSON Schema
- [x] 增加 project、flow、evidence 样例
- [x] 增加四档 Loop 样例
- [x] 增加最小校验入口
- [x] 运行校验并修正 Schema 或样例

## 交付与验证
- 交付物：`agentloop/schemas/`、`agentloop/examples/`、`agentloop/validate_examples.py`。
- 验证方式：运行全部样例的 Draft 2020-12 Schema 校验。

## 执行记录
- Schema 对顶层字段、Gate、执行步骤、档位互斥、子流程和子 Loop 定位做了约束。
- 七个样例文件已全部通过 Draft 2020-12 校验。
