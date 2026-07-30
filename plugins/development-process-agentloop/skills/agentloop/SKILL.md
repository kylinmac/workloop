---
name: agentloop
description: Execute a software-development request through the complete AgentLoop requirements, development, verification, Git, Gate, retry, recovery, composite, and epic protocols. Use when the user asks to start, continue, resume, inspect, or complete development work under AgentLoop, or explicitly invokes $agentloop.
---

# AgentLoop

Run the repository-backed development loop to a verified outcome. The installed
plugin contains a generated release snapshot of the complete protocol under
`references/`; `.agentloop/` in the target project is the runtime source of
truth. Chat history is never state.

Resolve `<plugin-root>` as the directory containing this plugin's
`.codex-plugin/plugin.json`. Run its control tool as:

```bash
python3 <plugin-root>/scripts/agentloop.py <command>
```

## Mandatory operating loop

For every turn:

1. Run `status` and load the selected `loop.yaml`.
2. Validate the current Loop before changing project files.
3. Read only the protocol reference needed for the current state and selected
   development or verification route.
4. Perform one checkable step allowed by the current state.
5. Inspect the real artifact, Git state, command result, or Gate event.
6. Record evidence and use `transition`; never edit `state` directly.
7. Continue until `done`, `cancelled`, a manual Gate, or a persisted `blocked`
   state.

Only the Loop coordinator updates the main state. The same Codex agent may act
as requirement, development, verification, and coordination roles in sequence,
but records the actual role in every operation.

## Start or resume

Run:

```bash
python3 <plugin-root>/scripts/agentloop.py doctor
python3 <plugin-root>/scripts/agentloop.py status
```

- If exactly one non-terminal Loop matches the request, resume it.
- If several are active and scope/worktree does not identify one, ask the user
  to choose.
- If none matches, initialize a Loop:

```bash
python3 <plugin-root>/scripts/agentloop.py init \
  --title "<request>" --level standard
```

Use `--level trivial` only when every trivial qualification is already known.
Use repeated `--subflow "<business deliverable>"` for a composite delivery.
Use `--kind epic --child "<independent delivery>"` for independently
deliverable child Loops.

The initializer requires a real Git baseline. For a non-Git project, inspect
the initial commit scope and sensitive files, obtain the `repository_bootstrap`
Gate from the user, initialize Git, create the checked baseline commit, then
rerun. Never blindly commit the whole directory.

## State work

Read `references/agentloop/AgentLoop状态机.md` for transition semantics and
`references/requirements/flows/需求确认流程.md` during requirement work.

| State | Required action |
| --- | --- |
| `draft` | Preserve the raw request, provisional execution profile, facts, and initial classification; transition to `clarifying`. |
| `clarifying` | Confirm facts, goal, scope, non-goals, rules, executable acceptance criteria, classification, prototype decision, and final execution profile. |
| `awaiting_requirement_confirmation` | Stop for a manual Gate unless the project's explicit automatic policy and all qualification checks pass. |
| `ready_for_development` | Inspect Git and existing implementation, route development and verification, and prepare standard or composite execution. |
| `development_preparing` | Produce only the selected flow's required pre-code artifacts and pass its entry check. |
| `developing` | Implement, build, statically check, add necessary unit tests, and create a traceable development commit. |
| `ready_for_verification` | Verify the handoff, commit, environment, data, accounts, and routed checks before accepting. |
| `verifying` | Execute targeted or flow verification and record real evidence. |
| `orchestrating` | Schedule subflows/child Loops, integrate verified commits, rerun per-delivery checks, run required integration verification, and aggregate. |
| `verified` | Obtain or automatically satisfy the configured completion Gate. |
| `blocked` | Preserve reason, owner, unblock condition, and resume state; resume only after rechecking the entry. |

Use the control command for every main transition:

```bash
python3 <plugin-root>/scripts/agentloop.py transition <loop-id> <target-state> \
  --actor <role> --reason "<checked reason>" --evidence <artifact-or-evidence-id>
```

Entering `blocked` also requires `--resume-state` and `--unblock-condition`.

## Classification, execution profile, and routing

Classification answers what changed. Execution profile answers how much
coordination is needed. Development routing answers which uncertainty must be
removed before coding. Do not collapse the three decisions.

Read:

- `references/requirements/需求分类.md`
- `references/agentloop/路由与阶段交接协议.md`
- `references/development/开发流程体系总览.md`

Choose exactly one main development flow:

| Route | Read |
| --- | --- |
| `quick-change` | `references/development/flows/快速变更流程.md` |
| `product-prototype` | `references/development/flows/产品原型驱动流程.md` |
| `business-process` | `references/development/flows/业务流程驱动流程.md` |
| `data-contract` | `references/development/flows/数据与契约驱动流程.md` |
| `domain-model` | `references/development/flows/领域模型驱动流程.md` |
| `architecture` | `references/development/flows/架构驱动流程.md` |
| `root-cause` | `references/development/flows/根因驱动修复流程.md` |
| `migration-compatibility` | `references/development/flows/迁移与兼容驱动流程.md` |
| `technical-validation` | `references/development/flows/技术验证驱动流程.md` |

Record routing with:

```bash
python3 <plugin-root>/scripts/agentloop.py route <loop-id> \
  --actor development-agent \
  --confidence high \
  --main-flow quick-change \
  --reason "<fact-based reason>" \
  --verification targeted \
  --verification-reason "<coverage and risk reason>"
```

Add only triggered `--supporting-flow` and `--required-output` values. Low
confidence makes `routing_confirmation` pending; stop for its Gate. A trivial
Loop is valid only with `quick-change`; any failed trivial condition upgrades
the execution profile and invalidates `self_check`.

Every new Loop explicitly records `prototype.implementation_basis`. When it is
true, record prototype type, structure/visual/interaction/content fidelity,
each prototype path and route, executable acceptance criteria, and justified
deviations. `product-prototype` requires
`prototype-implementation-matrix.yaml`; the control tool blocks development
until every page, region, control, interaction, state, data source, permission,
responsive rule, and deviation is complete.

Every new or re-confirmed Loop also declares `integration_data`. Enable it only
for frontend/backend features whose business display data should come from a
database. When enabled, frontend runtime records must come from the declared
backend APIs, and backend responses must query the declared database objects.
Verification seeds/factories/fixtures one unique sentinel into an isolated test
database and proves the same sentinel through database, API, and UI evidence.
Missing coverage or a mismatched sentinel blocks `verified` and parent
aggregation. Static UI copy, enums, and display configuration are excluded.

## Gates

Never infer approval from silence. Ask in the current Codex conversation and
record the resulting user event before proceeding:

```bash
python3 <plugin-root>/scripts/agentloop.py gate <loop-id> <gate-id> \
  --decision approved \
  --actor "<actual approver>" \
  --source codex-chat \
  --source-event-id "<current turn or host event id>" \
  --subject <project-relative-file>
```

The tool computes `sha256-manifest-v1`, stores the event, and binds the current
Gate to it. Never invent a human actor or source event. Destructive actions and
repository bootstrap are always manual.

## Git and concurrency

Read `references/rules/Git版本控制与可追溯规则.md` before the first project
write, worktree creation, merge, rollback, or delivery.

- Preserve user changes and never use destructive cleanup to manufacture a
  clean workspace.
- A non-concurrent trivial/standard Loop may use the current branch/worktree
  only when scope and user changes do not overlap.
- Concurrent, composite, and epic delivery units use separate branches and
  worktrees.
- Declare `scope.paths/interfaces/db_objects/states` before modification.
- Composite and same-repository epic work merge verified source commits into a
  parent integration branch. Rerun each delivery's targeted/flow checks on the
  integration head.
- If integration verification is required, run it on that same exact
  integration commit. If not required, the merge and post-merge checks are
  still mandatory.

## Verification and evidence

Read `references/verification/测试验证流程体系总览.md` and the routed executor:

| Executor | Read |
| --- | --- |
| `code` | `references/verification/flows/代码流程验证.md` |
| `ui` | `references/verification/flows/UI流程验证.md` |
| `command` | `references/verification/flows/命令与实验流程验证.md` |

- `self_check`: trivial + quick-change only; write the real command, output,
  and acceptance result to `work.md`, then reference it in the transition.
- `targeted`: run existing focused tests or commands and record evidence.
- `flow`: reuse or create a stable flow definition, executable automation, and
  real evidence.

For `visual` checks or high-fidelity prototypes, flow automation must be a real
project test/script, never a Markdown report. Record fixed viewport, comparison
method, allowed differences, pass criteria, and coverage from prototype page
through acceptance and automation step. Evidence records the same coverage
rows plus per-page reference/implementation files. Missing rows block
`passed`, `verified`, and parent aggregation.

Record targeted/flow runs:

```bash
python3 <plugin-root>/scripts/agentloop.py evidence <loop-id> \
  --check-id "<stable-check-id>" \
  --executor code \
  --result passed \
  --command-json '["npm","test","--","focused-test"]' \
  --exit-code 0 --duration-ms 1000 --environment local
```

Use `--flow-id` instead of `--check-id` for a reusable flow. Evidence must
match the current requirement version and exact tested commit. A model's
prediction is never evidence.

## Composite, epic, retry, and recovery

Read:

- `references/agentloop/执行重试与恢复协议.md`
- `references/agentloop/产物与目录协议.md`

Subflows are business-result slices inside one shared delivery Loop. Child
Loops are independently confirmable, deliverable, reversible, parallel, or
cross-repository units. Never split by controller/service/repository layers.

Keep each unit's scope, dependency, Git commit, verification route, handoff,
failure handoff, and failure-roundtrip count independent. On failure, rerun the
failed path, its normal path, affected branches, and required invariant
neighbors. Respect the configured retry and verification-roundtrip limits;
persist `blocked` when exhausted.

On resume, reconcile `loop.yaml`, Git, current execution, last transition,
artifacts, and evidence. If work completed but state did not advance, verify
and repair metadata without rerunning. If state advanced but artifacts are
missing, restore the last valid control state and record recovery.

When the completion Gate rejects prototype fidelity, use `--reason`, repeated
`--affected-page`, and repeated `--revalidation-scope`. The command marks only
related UI evidence stale, returns affected UI work to preparation, and keeps
the parent in orchestration.

## Completion

Before `verified -> done`:

1. Run `validate`.
2. Confirm all required validation and evidence are current and passed.
3. For composite/epic, confirm delivery-unit aggregation, verified integration
   commit, and integration verification.
4. Confirm the completion Gate.
5. Confirm the delivery commit is queryable and user changes are preserved.
6. Transition to `done`; the control tool releases the scope claim.

```bash
python3 <plugin-root>/scripts/agentloop.py validate
```

`done` means the development AgentLoop is complete; it does not mean the result
was released to production.
