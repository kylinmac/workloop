---
name: workloop-cn
description: 通过轻量的认知与证据闭环组织软件实现、重构、调试、迁移或恢复任务。适用于开始或恢复开发工作、澄清意图与假设、拆分可验证工作项、为共享模块或 Agent 边界建立契约，以及在完成前进行独立语义审查。
---

# Workloop 中文版

控制认知质量和证据真实性；具体实现方案仍由工程判断决定。

## 执行基本原则

1. 每个阶段只保留一个人类可读产物：`spec.md`、`plan.md`、`review.md`，以及项目级 `memory.md`。
2. 证据必须是实际命令输出、报告路径、截图、源码检查或人工确认，不能是 Agent 自我声明。
3. 影响范围或验收的假设必须在计划前关闭。
4. 必须由未参与实现的审查者对照需求、计划、差异和证据。
5. 一个干净上下文无法完成时拆分新的 Loop，不增加生命周期状态。
6. 把可复用失败变成可执行预防检查；重复出现后升级为测试、Lint、CI 或 Hook。
7. 错误记忆最多保留 20 条。
8. 只加载本路由、当前阶段 Skill、当前产物和匹配的记忆条目。

## 按状态路由

新需求从[需求模板](assets/templates/spec.md)创建 `.workloop/loops/wl-YYYYMMDD-NN/spec.md`，把当前提交写入 `base_commit`，然后使用 `workloop-spec`。

已有 Loop 先只读取 `spec.md` 中的 `status`：

| 状态 | Skill | 产物 |
|---|---|---|
| `clarifying` | `workloop-spec` | `spec.md` |
| `specified` | `workloop-plan` | `plan.md` |
| `executing` | `workloop-execute` | `plan.md` 的证据索引 |
| `reviewing` | 独立上下文中的 `workloop-review` | `review.md` |
| 审查通过 | `workloop-memory` | `.workloop/memory.md` |
| `blocked` | 仅在 `resume_when` 成立后返回 `blocked_from` | 无 |
| `done` 或 `cancelled` | 停止 | 无 |

状态只保存在 `spec.md` 前置元数据中。主路径是 `clarifying → specified → executing → reviewing → done`；`blocked` 与 `cancelled` 只按上述规则使用。

## 可选严格层

改变状态前运行：

```bash
python3 <workloop-plugin>/scripts/workloop.py check \
  --loop-dir .workloop/loops/<loop-id> --target <status>
```

分配工作项前生成投影：

```bash
python3 <workloop-plugin>/scripts/workloop.py project \
  --loop-dir .workloop/loops/<loop-id> --work-item T1
```

契约、投影和机器门禁都是可选严格能力，方法本身不能依赖插件。仅在填写产物不明确时读取[完整示例 Loop](references/example-loop/spec.md)，日常路由时不要加载示例。
