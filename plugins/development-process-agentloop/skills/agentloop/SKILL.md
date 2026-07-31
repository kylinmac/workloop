---
name: agentloop
description: Route an AgentLoop-controlled software task to its current phase without loading the full lifecycle or complete loop history.
---

# AgentLoop Router

Use this thin router when starting, resuming, inspecting, or completing an
AgentLoop task. The control program and schemas enforce the rules; do not load
the entire protocol into the model context.

Resolve `<plugin-root>` as the directory containing `.codex-plugin/plugin.json`.

## Resume

Run:

```bash
python3 <plugin-root>/scripts/agentloop.py status
python3 <plugin-root>/scripts/agentloop.py context <loop-id>
```

`context` verifies the protected `loop.yaml`, then returns only the current
phase projection, its source digest, and `phase_skill`. Read that one phase
skill completely. Do not read full `loop.yaml`, transition history, Gate event
history, Evidence bodies, or unrelated protocol references unless the recovery
skill or a concrete validation error requires them.

For a composite subflow, request its isolated projection:

```bash
python3 <plugin-root>/scripts/agentloop.py context <loop-id> --subflow-id <id>
```

## Start

If no matching active Loop exists:

```bash
python3 <plugin-root>/scripts/agentloop.py doctor
python3 <plugin-root>/scripts/agentloop.py init --title "<request>" --level standard
```

Use `trivial` only when every qualification is known. Use repeated `--subflow`
for composite delivery and `--kind epic --child` for independent child Loops.
Repository bootstrap remains a manual Gate.

## Common control rules

- `.agentloop/` is the durable source of truth; `context` is a read-only view.
- Validate before project writes and after control changes.
- Change state only through `transition`; never edit state, Gate, Evidence
  validity, integration checkpoint, or subflow state directly.
- Record only real command execution as Evidence and bind it to the tested Git
  commit.
- Preserve user changes. Destructive actions require their configured Gate.
- Continue until `done`, `cancelled`, a manual Gate, or an explicit `blocked`
  state.

Phase mapping:

| Projection phase | Skill |
|---|---|
| requirements | `development-process-agentloop:agentloop-requirements` |
| development | `development-process-agentloop:agentloop-development` |
| verification | `development-process-agentloop:agentloop-verification` |
| integration | `development-process-agentloop:agentloop-integration` |
| completion | `development-process-agentloop:agentloop-completion` |
| recovery | `development-process-agentloop:agentloop-recovery` |
