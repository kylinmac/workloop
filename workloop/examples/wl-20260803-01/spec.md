---
loop: wl-20260803-01
status: done
title: 退款申请支持重复提交保护
created: 2026-08-03
base_commit: 3f8a1c2
---

## 意图

用户在退款页面快速点击两次"提交"，或网络重试导致同一申请到达两次时，系统只创建一条退款申请，第二次请求返回已存在的申请，不报错、不重复扣减。

**非目标**：不处理不同用户对同一订单的并发退款（已有订单锁覆盖）；不改前端按钮防抖。

## 事实与假设

事实：

- 退款申请入口是 `POST /api/refunds`，落库表 `refund_applications` —— 来源：`src/api/refunds.py`、`migrations/0042_refunds.sql`
- 表上目前没有防重唯一约束 —— 来源：`\d refund_applications` 输出，见 A1 证据

假设：

| ID | 假设 | 影响 | 状态 | 验证方式 / 关闭证据 |
|---|---|---|---|---|
| A1 | 数据库层可以用 (order_id, user_id, status='pending') 部分唯一索引防重 | 实现 | confirmed | psql 试建索引成功，见 plan T1 证据 |
| A2 | 重复请求应返回 200 + 已有申请，而不是 409 | 验收 | confirmed | 用户答复："返回已有申请，前端不需要感知重复"（2026-08-03 对话） |
| A3 | 现有客户端不依赖重复提交产生多条记录 | 范围 | confirmed | 全库搜索无消费方按条数计费；用户确认无此依赖 |

## 风险

最大不确定性：并发窗口内两个请求同时通过存在性检查。对应验证手段：并发测试用 20 个协程同时提交同一申请，断言库中只有一条。

## 验收标准

- [x] AC1: 同一用户对同一订单连续两次提交，第二次返回 200 且 `refund_id` 与第一次相同 —— 验证：`pytest tests/api/test_refunds.py::test_duplicate_submit`
- [x] AC2: 20 个并发请求提交同一申请，`refund_applications` 中只有一条 pending 记录 —— 验证：`pytest tests/api/test_refunds.py::test_concurrent_submit`
- [x] AC3: 不同订单的退款申请不受影响 —— 验证：`pytest tests/api/test_refunds.py -k "not duplicate and not concurrent"`
