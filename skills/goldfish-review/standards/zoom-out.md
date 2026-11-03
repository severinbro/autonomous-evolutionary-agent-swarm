# Zoom-Out Standard

A design passes when it solves the root problem in the simplest way that fits the codebase.

1. **Objective.** A reader can state what the design achieves and why. If not, the review stops here.
2. **Root cause.** The design fixes the underlying problem, not a symptom, and fits the project's stated goals.
3. **Simplicity.** No features, options or abstractions for needs nobody stated. No caching, queues, sharding or other optimisation without a measured bottleneck. Data passes through as few components as possible.
4. **Altitude.** High-level sections describe components, interfaces and data flow; code-level detail belongs in the implementation plan.
5. **Placement.** New logic sits in the layer and component where it belongs.
6. **Reuse.** Existing code, standard libraries and established packages are used before new code is written; existing patterns are followed.
