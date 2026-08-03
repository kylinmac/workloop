---
name: workloop-controls-cn
description: 执行 Workloop 协议中可以确定性判断的部分。适用于检查 Loop 状态转换、验证 AC 或契约覆盖、生成隔离工作项投影、诊断门禁失败，或阻止活动工作项声明范围之外的修改。
---

# Workloop 控制层

控制脚本只判断结构和引用；业务语义仍由独立审查判断。

把 `<plugin-root>` 解析为包含 `.codex-plugin/plugin.json` 的目录。

检查当前或目标状态：

```bash
python3 <plugin-root>/scripts/workloop.py check \
  --loop-dir .workloop/loops/<loop-id> [--target <status>]
```

只能通过受检转换命令改变状态：

```bash
python3 <plugin-root>/scripts/workloop.py transition \
  --loop-dir .workloop/loops/<loop-id> --to <status>
```

实现或委派前生成工作包：

```bash
python3 <plugin-root>/scripts/workloop.py project \
  --loop-dir .workloop/loops/<loop-id> --work-item T1
```

投影只包含选定工作项、依赖、引用的 AC、假设、契约、证据和明确选择的记忆条目。

门禁通过只代表结构有效，不能证明需求、代码行为、审查者独立性或外部证据真实。`workloop-review` 仍必须执行语义对照并重跑关键检查。
