# Learn from failed execution

Create one failure card for each active or historical failed Evidence that affected the task.

Record:

- the failed Evidence ID;
- the observable mistake;
- the actual reason rather than the surface symptom;
- affected cognition and decision IDs, or an explicit `unlinked_reason`;
- a concrete prevention change;
- re-verification Evidence IDs.

Update the relevant cognition item or work plan. “Be more careful” is not a prevention. Prefer a contract clarification, executable assertion, type/schema constraint, data invariant, guardrail, or changed work decomposition.

Keep the card `open` until at least one referenced re-verification Evidence is active and passed. Then mark it `prevention_verified`. Do not delete the failed Evidence after a later successful run; the compact card is the recovery memory.
