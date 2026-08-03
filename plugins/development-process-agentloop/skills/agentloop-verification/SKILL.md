---
name: agentloop-verification
description: Handle only AgentLoop verification handoff, executable checks, Evidence, and verification failure round trips.
---

# AgentLoop Verification

Use for `ready_for_verification` and `verifying`, including a focused subflow.
Work from the `context` projection and active Evidence summaries.

Read only:

- `references/verification/测试验证流程体系总览.md`;
- the executor file actually selected under `references/verification/flows/`;
- `references/agentloop/执行重试与恢复协议.md` only after failure.

Check the handoff, exact tested commit, environment, data, accounts, acceptance
mapping, and selected flow/check identity. Run the real command through
`evidence`; never submit a handwritten passed report.

For high-fidelity or visual work, cover every declared page, interaction, and
navigation branch through browser actions from the source route. Direct target
URLs are setup, not interaction proof. Visual and business results remain
independent. Server mutations must prove API success, database/readback state,
refresh, relogin, failure, permission, downstream use, and audit behavior.

Only complete active Evidence bound to the current requirement and tested
commit permits `verifying → verified` or subflow `verifying → passed`. On
failure, stale only affected Evidence and return to the narrowest development
state.

When a collaboration contract is required, the generated test report must
include `contract_consistency` for every contract ID, both provider and
consumer implementation paths, all declared participants, the confirmed
digest, and zero semantic violations.

Do not load classification details, Gate event history, unrelated executors,
or parent integration details.
