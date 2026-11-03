# Implementation-Readiness Standard

An implementation plan passes when an engineer (or a fresh agent) unfamiliar with the codebase can carry it out correctly on the first attempt, without asking questions or making design choices.

1. **Zero decisions.** The plan leaves no design or architecture choice to the implementer: schemas, interfaces, error behaviour, dependencies and edge-case handling are decided in the plan.
2. **Files.** Every task lists the exact repository paths it creates, modifies or deletes, each tagged `(Create)`, `(Modify)` or `(Delete)`. Nothing outside the list changes.
3. **Changes.** Each task says what changes in each file and why, at the level of functions, fields and behaviour.
4. **Verification.** Each task has a runnable verification command that fails without the change, and names its test cases: the normal case and the edge cases.
5. **Order.** Tasks state their dependencies, and each task leaves the code buildable with its tests passing.
