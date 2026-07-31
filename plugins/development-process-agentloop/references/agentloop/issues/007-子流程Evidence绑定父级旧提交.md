# 子流程 Evidence 绑定父级旧提交

## 现象

子流程本次 Evidence 已绑定当前提交，但校验仍拿父级旧 `integration.delivery_commit/head_commit` 比较并拒绝。

## 影响

真实通过的子流程无法合法进入 passed。

## 根因

测试提交选择函数没有区分子流程验证与父流程集成验证。

## 旧门禁为何没拦截

单 Loop 测试只覆盖父级提交来源，没有覆盖子流程最近一次 verifying transition。

## 修复

子流程 tested commit 取该子流程最近一次进入 verifying 的 transition commit；父流程仍取集成 checkpoint。

## 回归

父级集成提交落后、子流程 verifying 提交为当前 HEAD 时，子 Evidence 应通过且父级仍受 checkpoint 约束。

## 预防规则

提交绑定必须先确定验证作用域，再选择该作用域的合法提交。
