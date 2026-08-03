# Workloop

Workloop 是一套轻量的软件开发认知闭环：先固定意图、假设、风险和验收，再按工作项执行，用独立视角核对实现语义与真实证据，最后只沉淀可复用的失败教训。

仓库只保留两个产品层：

- `workloop-skills/`：方法层。六个可独立触发的 Skill 和四个 Markdown 模板，不依赖插件也能使用。
- `workloop-plugin/`：控制层。提供工作项投影、可选共享 Contract、确定性 Gate 和最小 Hook。

项目运行时产物固定在：

```text
.workloop/
├── memory.md
└── loops/<loop-id>/
    ├── spec.md
    ├── plan.md
    └── review.md
```

原 AgentLoop、旧 Schema、历史问题清单、流程分类文档和大型控制器已经移除；需要追溯时使用 Git 历史。

## 快速验证

```bash
python3 workloop-plugin/scripts/workloop.py check --loop-dir .workloop/loops/<loop-id>
python3 workloop-plugin/scripts/workloop.py project --loop-dir .workloop/loops/<loop-id> --work-item T1
python3 -m unittest discover -s workloop-plugin/tests -v
```

完整协议与职责边界见 `docs/protocol.md`。
