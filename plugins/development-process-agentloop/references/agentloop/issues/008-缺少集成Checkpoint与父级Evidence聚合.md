# 缺少集成 Checkpoint 与父级 Evidence 聚合

## 现象

父级 `integration.head_commit` 无合法命令更新；已通过子流程 Evidence 不被父级聚合，父级又不能在 verified 状态补 Evidence。

## 影响

Composite Loop 在全部子流程真实通过后仍无法合法完成。

## 根因

集成提交更新和父级验证被设计成隐式字段编辑，Evidence 查询只看父级作用域。

## 旧门禁为何没拦截

只验证子流程 state == passed，没有覆盖父级在新集成提交上的证据聚合路径。

## 修复

增加 integration-checkpoint 命令；父级聚合当前需求版本、当前集成提交且已通过子流程的 Evidence。

## 回归

checkpoint 前父级拒绝，checkpoint 后相同提交上的完整子 Evidence 可聚合通过。

## 预防规则

所有集成基线变化必须有合法命令和提交绑定，Composite 验证必须按作用域聚合。
