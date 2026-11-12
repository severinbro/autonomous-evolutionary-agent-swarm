# Implementation-Readiness Standard

An implementation plan passes when an engineer (or a fresh agent) unfamiliar with the codebase can carry it out correctly on the first attempt, without asking questions or making design choices.

1. **Zero decisions & zero open questions.** The document contains no `Open Questions` section or unresolved `[?]` prompts (questions belong in live Elephant polls before review), and leaves no design choice to the implementer: schemas, interfaces, error behaviour, dependencies and edge-case handling are settled in the plan.
2. **Files.** Every task lists the exact repository paths it creates, modifies or deletes, each tagged `(Create)`, `(Modify)` or `(Delete)`. Nothing outside the list changes.
3. **Changes.** Each task states what changes in each file and why, at the level of functions, fields and behaviour, preferring standard library and existing helpers over speculative abstractions (YAGNI).
4. **Red-Green-Refactor Verification.** Each task has a runnable `Verification` command that fails before the change and passes after, naming both normal and edge test cases.
5. **Vertical slices & order.** Tasks decompose into buildable vertical slices, state their `Depends on` dependencies, and keep tests passing after each task.
