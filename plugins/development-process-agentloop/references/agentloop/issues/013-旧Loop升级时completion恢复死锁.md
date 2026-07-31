# 旧 Loop 升级时 completion 恢复死锁

## 现象

旧版已 verified 的原型 Loop 没有 behavior inventory。新版执行 completion rejection 时先强制校验 inventory，因此不能退回准备态；而 `prototype-scan` 又只能在退回后运行。

## 影响

发现原型偏差后既不能合法恢复，也不能生成新版必需产物，形成升级死锁。

## 根因

恢复路径复用了面向编码/验证的严格矩阵加载器，没有区分“读取旧矩阵定位影响范围”和“证明新版编码准备完成”。

## 旧门禁为何没拦截

回归只覆盖新建 Loop，测试数据在 completion rejection 前已经包含新版 inventory。

## 修复

矩阵加载器保留严格默认；completion rejection 仅在定位受影响页面时跳过 inventory 检查。恢复进入 `development_preparing/orchestrating` 后，所有正常 Gate 仍强制生成并校验 inventory。

## 回归

从已 verified、无 inventory 的旧 Loop 发起原型 completion rejection 必须成功；随后未执行 `prototype-scan` 时仍不得进入 developing。

## 预防规则

新增编码前必需产物时，必须同时测试旧版本终态的拒绝、恢复和迁移路径。
