---
name: workloop-review
description: Independently verify a Workloop implementation against intent, acceptance, assumptions, Contracts, diff, and evidence. Use when status is reviewing, when dispatched as a non-executing reviewer, or when semantic consistency and evidence freshness must be checked before completion.
---

# Workloop Review

Copy `../workloop/assets/templates/review.md` to `.workloop/loops/<id>/review.md`. Do not perform this review if you implemented the change.

Read only `spec.md`, `plan.md`, `git diff <base_commit>..HEAD`, referenced raw evidence, and matching source files. Do not use the executor's conversation narrative as proof.

1. Check every AC has a work item.
2. Check the diff implements the AC's actual behavior, not merely a similarly named symbol.
3. Check every Evidence row points to real, fresh output matching its method.
4. Check assumption classification and closure evidence; find rejected assumptions whose effects remain.
5. Check the diff stays within intent and active work-item scopes.
6. Check the largest risk and every Contract have meaningful verification.

Re-run one or two critical validations independently. Record an external reviewer anchor and actual results.

Return only `pass` or `fail`. On failure, list each problem and return location: `executing` for implementation/evidence problems, `clarifying` for intent or assumption problems. On pass, recommend a memory entry only for a real, reusable failure with an executable prevention check.
