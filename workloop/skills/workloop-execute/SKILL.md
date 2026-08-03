---
name: workloop-execute
description: Use when a loop is in executing status and tasks from plan.md are being implemented, or when tempted to check off a task without running its verification.
---

# Workloop Execute：执行循环

## 循环体

对 plan.md 的每个任务：

```text
实现 → 真实运行该任务的验证命令 → 把命令和关键输出贴进"证据" → 勾选 → git 提交
```

一个任务一个循环，不批量。提交信息引用任务号（如 `T2: ...`）。证据必须带日期或紧邻的提交 hash——没有时间锚的证据 review 时按过期处理。

## 证据铁律

**没有贴出真实输出的任务不算完成。** 勾选的唯一依据是证据栏里有本次运行的命令输出、截图路径或用户确认原话。

| 合理化借口 | 现实 |
|---|---|
| "改动太小，不用跑验证" | 小改动的验证也只要几秒。跑。 |
| "我刚才手动看过了" | 没有留下输出的验证等于没验证。重跑并贴输出。 |
| "先把任务都做完，最后统一验证" | 批量验证掩盖单个任务的失败点。一任务一验证。 |
| "验证命令环境有问题，先勾上" | 环境问题就是阻塞。修环境或标 blocked，不勾选。 |

## 偏离处理

- 发现 spec 假设被推翻：更新假设表为 rejected 并写影响，若波及范围/验收，status 退回 `clarifying`。
- 需要新任务或删任务：改 plan.md 并在执行日志记一行。
- 卡住无法推进：status 改 `blocked`，并在 spec frontmatter 写 `blocked_from: executing` 和 `resume_when: <恢复条件>`，停止而不是绕过。

全部任务勾选且有证据、工作已提交后，把 status 改为 `reviewing`，并按 workloop-review 的**派发协议**发起独立审查——审查本身不是你的工作（宪法第 4 条），你只负责派发和事后按结论机械执行。
