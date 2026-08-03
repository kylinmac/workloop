---
loop: wl-20260803-01
status: done
title: 持久化用户并返回其标识符
created: 2026-08-03
base_commit: abc1234
---

## 意图

`POST /users` 持久化用户，并返回能够读取同一记录的标识符。

**非目标：** 不包含用户界面和批量导入。

## 事实与假设

事实：

- 路由已存在。— 来源：`src/users.py`
- 客户端已调用 `POST /users`。— 来源：`web/api/users.ts`

| ID | 假设 | 影响 | 状态 | 证据或来源 |
|---|---|---|---|---|
| A1 | 测试数据库中存在用户表 | implementation | confirmed | `migrations/001_users.sql` |

## 最大风险

序列化后返回的标识符可能无法匹配持久化记录。— 验证：运行创建并读取同一用户的集成测试。

## 验收标准

- [x] `AC1` — `POST /users` 返回持久化标识符
  - 验证：`pytest tests/test_users.py::test_create_returns_persisted_id`
- [x] `AC2` — 客户端从约定响应字段读取标识符
  - 验证：`npm test -- users-api.test.ts`
