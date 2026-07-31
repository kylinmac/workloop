# 集成验证 required 分支语义不一致

## 现象

Git 规则线性步骤写成总要执行跨切片验证，后文又允许 `required: false` 时只做合并后检查。

## 影响

运行引擎可能在无需跨切片验证时仍强跑额外测试，或不同实现产生不同状态。

## 根因

叙述性主路径没有显式表达 `integration_verification.required` 条件分支。

## 旧门禁为何没拦截

文档检查只看局部表述，没有做同字段跨章节语义一致性校验。

## 修复

集成步骤按 required 分支；重跑切片验证改为按该切片 targeted/flow 策略执行。

## 回归

`required: false` 仅要求合并后检查；`required: true` 才要求同一 integration head 上的跨切片验证。

## 预防规则

条件字段必须在主流程、状态机和示例中使用相同分支语义。
