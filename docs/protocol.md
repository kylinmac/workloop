# Workloop Minimal Protocol

## Goal

Workloop controls only two things: whether cognition is reliable enough to act on and whether a completion claim has real evidence. It does not replace engineering judgment or create a separate process for every task type.

## Four stages and fixed artifacts

| Stage | Artifact | Required answers |
|---|---|---|
| Understanding | `spec.md` | Goal, non-goals, facts, blocking assumptions, maximum risk, and acceptance criteria |
| Planning and execution | `plan.md` | Work items, scope, dependencies, AC mapping, verification, and Evidence index; add Contracts only for shared boundaries |
| Independent verification | `review.md` | Whether ACs, plan, implementation, and Evidence are semantically consistent; whether scope was exceeded; whether the maximum risk was truly tested |
| Failure learning | `.workloop/memory.md` | Which trigger can recur and which executable prevention check should run |

Do not paste raw logs, screenshots, or test reports into `plan.md`. Evidence records only a stable ID, result, observation time, source path, and covered AC or Contract IDs. Read the raw source only when needed.

## Minimal state machine

```text
clarifying → specified → executing → reviewing → done
```

- `blocked` pauses the current phase. Record `blocked_from` and `resume_when`, then return to the prior phase when the condition is true.
- `cancelled` is terminal.
- Store state only in the `spec.md` frontmatter.

## Consistency relationships

Check only six traceable relationships before completion:

1. intent ↔ acceptance criteria;
2. acceptance criteria ↔ work items;
3. blocking assumptions ↔ closure evidence;
4. shared Contracts ↔ provider and consumer work items;
5. acceptance criteria and Contracts ↔ valid Evidence;
6. failure causes ↔ executable prevention checks.

The plugin checks structural integrity. A reviewer who did not perform the implementation checks whether the behavior is what the user actually requested. The plugin must never treat the presence of a string as proof of semantic correctness.

## Instantiate only when needed

- Create no Contract when there is no shared boundary.
- Add no memory entry when there was no real failure or independent defect.
- Generate no work-item projection when there is only one work item and no delegation boundary.
- Create no quality metric when the requirement has no quantitative target.
- Split work into another Loop when one clean context cannot finish it; do not extend the state machine.

## Skill and plugin boundary

`workloop-skills/` defines the method for understanding, planning, execution, independent review, and failure learning. It remains human-readable, independently usable, and loaded one phase at a time.

`workloop-plugin/` fixes only rules that a machine can reliably judge: state, required sections, stable IDs, AC coverage, blocking assumptions, reciprocal Contract references, Evidence references, work-item scope, and review structure. It must not restore the full knowledge-state model, complex schema family, failure-card ledger, or legacy control snapshots.

## Language policy

English is the canonical executable source because parser keys, status values, command interfaces, and cross-agent handoffs benefit from one stable vocabulary. `workloop-cn/` mirrors every human-facing source in Chinese for reading and comparison. Runtime code and plugin discovery never load the companion directory.
