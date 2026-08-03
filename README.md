# Workloop

Workloop is a lightweight cognition-and-evidence loop for software development. It fixes intent, assumptions, risk, and acceptance before implementation; executes one scoped work item at a time; independently compares behavior with real evidence; and retains only reusable lessons from real failures.

The repository has two executable layers:

- `workloop-skills/`: the method layer. Six independently triggerable skills, four Markdown templates, and one complete example loop. It works without the plugin.
- `workloop-plugin/`: the strict layer. It packages the method skills and adds work-item projection, optional shared Contracts, deterministic gates, and a minimal scope hook.

Runtime artifacts use this fixed layout:

```text
.workloop/
├── memory.md
└── loops/<loop-id>/
    ├── spec.md
    ├── plan.md
    └── review.md
```

English is the canonical executable source. `workloop-cn/` is a complete Chinese reading companion with the same human-facing documents, skills, templates, and example paths. It is intentionally excluded from plugin discovery so the two languages cannot drift into competing runtime rules.

The former AgentLoop, legacy schemas, historical issue catalog, process taxonomy, and large controller are available only through Git history.

## Quick validation

```bash
python3 workloop-plugin/scripts/workloop.py check --loop-dir .workloop/loops/<loop-id>
python3 workloop-plugin/scripts/workloop.py project --loop-dir .workloop/loops/<loop-id> --work-item T1
python3 -m unittest discover -s workloop-plugin/tests -v
```

See `docs/protocol.md` for the complete protocol and responsibility boundary.
