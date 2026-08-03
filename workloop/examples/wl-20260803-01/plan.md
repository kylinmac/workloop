# Plan：退款申请支持重复提交保护

对应 spec：`spec.md`

## 风险应对

并发窗口风险由 T1 的数据库唯一索引（根本防线）+ T3 的并发测试（验证）覆盖；应用层检查只是快速路径。

## 任务

- [x] T1（覆盖 AC2）：迁移脚本增加部分唯一索引 `(order_id, user_id) WHERE status = 'pending'`
  - 验证：`alembic upgrade head && psql -c "\d refund_applications"`
  - 证据：
    ```text
    $ alembic upgrade head
    INFO  Running upgrade 0042 -> 0043, add refund dedup index
    $ psql -c "\d refund_applications" | grep dedup
    "uq_refund_pending_dedup" UNIQUE, btree (order_id, user_id) WHERE status = 'pending'
    ```
- [x] T2（覆盖 AC1）：`POST /api/refunds` 捕获唯一冲突，改查已有 pending 申请并返回 200
  - 验证：`pytest tests/api/test_refunds.py::test_duplicate_submit`
  - 证据：
    ```text
    $ pytest tests/api/test_refunds.py::test_duplicate_submit -q
    1 passed in 0.41s
    ```
- [x] T3（覆盖 AC2）：并发测试：20 协程同时提交，断言单条记录
  - 验证：`pytest tests/api/test_refunds.py::test_concurrent_submit`
  - 证据：
    ```text
    $ pytest tests/api/test_refunds.py::test_concurrent_submit -q
    1 passed in 1.87s
    ```
- [x] T4（覆盖 AC3）：回归：其余退款测试全绿
  - 验证：`pytest tests/api/test_refunds.py -q`
  - 证据：
    ```text
    $ pytest tests/api/test_refunds.py -q
    14 passed in 3.02s
    ```

## 执行日志

- 2026-08-03 T2 实现时发现初版用"先查后插"，并发测试失败一次；改为依赖唯一冲突捕获后通过。计划未变。
