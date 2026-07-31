---
name: agentloop-recovery
description: Handle only AgentLoop blocked, failed, interrupted, tampered, upgraded, or inconsistent-state recovery.
---

# AgentLoop Recovery

Use for `blocked`, failed subflows, missing snapshots, interrupted operations,
runtime upgrades, or control inconsistencies. Begin with the recovery
projection; it includes the blocker, resume state/phase, current execution,
failure handoff, compact Git identity, and last transition only.

Read only the reference matching the failure:

- `references/agentloop/执行重试与恢复协议.md` for retries and blocked recovery;
- `references/agentloop/产物与目录协议.md` for missing/malformed artifacts;
- `references/rules/Git版本控制与可追溯规则.md` for Git divergence;
- the relevant issue document only when its exact failure recurs.

Reconcile the stated blocker against real files, Git, commands, and Evidence.
If work completed but metadata did not, repair metadata without rerunning. If
state advanced without artifacts, restore the last trusted control state.
Use `runtime-upgrade` for installed-runtime drift and `repair-control` only from
a trusted commit; never rebuild a missing snapshot from mutable current state.

After satisfying the unblock condition, resume at the recorded state and load
that phase's projection and skill. Read full `loop.yaml` only when the compact
projection cannot diagnose a concrete control inconsistency.
