# 非视觉 Flow 被错误纳入视觉 Gate

## 现象

父级聚合时把代码、构建或其他非视觉 flow 的 coverage 当作视觉 coverage，产生错误缺失或补偿。

## 影响

视觉 Gate 既可能误报失败，也可能被无关 Evidence 干扰。

## 根因

聚合集合按已选 flow 全量计算，没有先按 `visual` 检查能力筛选。

## 旧门禁为何没拦截

测试只使用全视觉 flow，没有混合多种验证 flow。

## 修复

视觉期望、flow coverage 和 Evidence IDs 只来自明确要求 visual 的 flow。

## 回归

Composite 同时选择 UI、代码和构建 flow 时，视觉 Gate 只计算 UI flow。

## 预防规则

每个 Gate 只能消费声明了对应检查能力的 Evidence。
