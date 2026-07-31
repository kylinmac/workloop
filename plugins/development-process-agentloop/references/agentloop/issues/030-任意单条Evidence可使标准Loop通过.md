# 任意单条 Evidence 可使标准 Loop 通过

## 现象
standard Loop 只要存在一条 active/passed Evidence 就能进入 `verified`。
## 影响
未覆盖的验收标准被静默遗漏。
## 根因
自由文本需求没有形成可聚合的验收义务集合。
## 旧门禁为何没拦截
控制器只判断 Evidence 存在，不计算必需验收 ID 的集合差。
## 修复
增加 `acceptance_obligations`、实现及 flow/check 映射、Evidence `acceptance_ids`，并在子流程、父流程和 verified Gate 全量聚合。
## 回归
两个必需义务只覆盖一个时失败，同一当前运行覆盖两项后通过。
## 预防规则
任何完成结论都必须从独立验收基线重算覆盖集合。
