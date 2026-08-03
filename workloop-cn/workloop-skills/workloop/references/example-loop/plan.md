# 计划：持久化用户并返回其标识符

## 风险覆盖

- 最大风险：序列化后返回的标识符可能无法匹配持久化记录。
- 覆盖方式：T1 集成验证和 EV1。

## 契约

### CT1 — 新建用户标识符

- 声明：成功的 `POST /users` 响应通过 `userId` 暴露持久化标识符。
- 供给方：后端用户接口
- 消费方：Web API 客户端
- 工作项：T1, T2
- 验证：通过接口创建用户，并通过客户端夹具读取 `userId`
- 证据：EV1, EV2

## 工作项

### T1 — 持久化并返回用户标识符

- 状态：done
- 覆盖：AC1
- 假设：A1
- 依赖：none
- 范围：`src/users.py`, `tests/test_users.py`
- 契约：CT1
- 记忆：M1
- 输出：包含持久化 `userId` 的接口响应
- 验证：`pytest tests/test_users.py::test_create_returns_persisted_id`
- 证据：EV1

### T2 — 消费共享标识符字段

- 状态：done
- 覆盖：AC2
- 假设：none
- 依赖：T1
- 范围：`web/api/users.ts`, `web/api/users-api.test.ts`
- 契约：CT1
- 记忆：none
- 输出：客户端对 `userId` 响应字段的映射
- 验证：`npm test -- users-api.test.ts`
- 证据：EV2

## 证据索引

| ID | 结果 | 观察时间 | 来源 | 覆盖 |
|---|---|---|---|---|
| EV1 | pass | 2026-08-03 / def5678 | `reports/users-integration.txt` | AC1, CT1 |
| EV2 | pass | 2026-08-03 / def5678 | `reports/users-client.txt` | AC2, CT1 |

## 执行日志

- 2026-08-03 — 没有偏离已明确范围。
