# 新 Evidence 未淘汰同范围旧记录

## 现象

同一需求版本、子流程和 flow 的 Evidence 46 已通过，但旧提交上的 Evidence 45 仍保持 active，passed Gate 消费旧记录后拒绝推进。

## 影响

重跑成功无法替代旧结果，子流程被错误卡在 verifying。

## 根因

Evidence 命令只追加运行记录，没有定义同一验证范围内的新旧替代关系。

## 旧门禁为何没拦截

回归只记录一次 Evidence，没有覆盖同 flow 在新提交上重跑。

## 修复

写入新 Evidence 前，将同 requirement、subflow、flow/check 范围内的旧 active 记录标记 stale，再追加新记录。

## 回归

同一 flow 连续运行两次后只能有最新记录 active，Gate 必须绑定最新测试提交。

## 预防规则

追加式审计日志必须同时定义确定性的“当前有效记录”选择规则。
