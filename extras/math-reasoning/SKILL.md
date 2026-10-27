---
name: math-reasoning
description: Query the local GPU-accelerated Limite 1B - Violetto model for mathematical proofs, Olympiad problems, collision geometry, and game physics equations.
disable-model-invocation: false
triggers: [user, model]
---

# Local Mathematical & Physics Reasoning (Limite 1B - Violetto)

Use this skill whenever an orchestrator or subagent requires rigorous mathematical evaluation, trigonometric physics, coordinate projections, or algorithmic proofs.

The model runs locally on **GPU 0** via vLLM and incurs zero API token costs.

---

## 1. Quick Execution

To solve a problem, pass the query as a string argument:

```bash
/mnt/sda/development/scripts/math_eval.py "Calculate the reflection vector of velocity V = (3, -4) off a surface with normal N = (0, 1)."
```

For complex multiline equations:
```bash
/mnt/sda/development/scripts/math_eval.py << 'EOF'
Given a sphere of radius R at position P1 and a ray starting at P0 with direction D,
derive the discriminant formula to check for intersection.
EOF
```

To parse machine-readable JSON output:
```bash
/mnt/sda/development/scripts/math_eval.py --json "Find the roots of x^2 - 5x + 6 = 0"
```

---

## 2. Server Management

The server auto-starts if offline, but can be controlled directly:
```bash
# Check status:
/mnt/sda/development/scripts/limite_ctl.sh status

# Start manually:
/mnt/sda/development/scripts/limite_ctl.sh start

# Stop:
/mnt/sda/development/scripts/limite_ctl.sh stop
```

---

## 3. Fallback on Non-GPU / Other Machines

If running on a machine where `/mnt/sda/development/scripts/math_eval.py` is not present:
* Solve the mathematical problem natively within your LLM reasoning.
* To verify calculations numerically or algebraically, execute a local Python one-liner:
  ```bash
  python3 -c "import math, sympy; ..."
  ```
* Do not fail or block if the local Limite script is unavailable.
