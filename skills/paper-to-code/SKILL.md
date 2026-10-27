---
name: paper-to-code
description: "Use when implementing an equation, algorithm, estimator, or theorem from a scientific paper in Zotero or on arXiv, and the result needs verified reference code and tests."
disable-model-invocation: false
triggers: [user, model]
---

# Paper-to-Code Mathematical & Algorithmic Extractor (`/paper-to-code`)

> **Script paths:** `$AGENT_SWARM_HOME` is the root of this skill pack (the folder containing `skills/` and `scripts/`). If it is unset, resolve this file's real path (following symlinks) and go two directories up.

Use this skill **standalone** or prior to / during `/invoke-swarm` whenever a task requires implementing a formal mathematical model, physical equation, statistical estimator, or algorithm from a scientific paper in the user's **Zotero library** or **arXiv/OpenAlex**.

---

## 1. End-to-End Extraction & Verification Workflow

### Step 1: Extract Formal Equations & Pseudocode from the Paper
1. **From Personal Zotero Library (`scripts/zotero_tool.py`):**
   ```bash
   # Search for the target paper:
   python3 "$AGENT_SWARM_HOME/scripts/zotero_tool.py" search "<paper or topic>"
   # Extract user highlights/annotations (often marking the key equations!):
   python3 "$AGENT_SWARM_HOME/scripts/zotero_tool.py" notes <ITEM_KEY>
   # Extract full text or grep for equations/algorithms inside the cached PDF:
   python3 "$AGENT_SWARM_HOME/scripts/zotero_tool.py" pdf <ITEM_KEY> --grep "Algorithm|Equation|Theorem|Proposition"
   ```
2. **From arXiv / Open Literature:**
   Use `literature-search-arxiv` or `literature-search-europepmc` to retrieve the paper's full text or LaTeX source.

### Step 2: Cross-Verify Mathematical Derivations & Boundary Cases
Before writing application code, verify the equation's closed-form behavior, dimensional consistency, and boundary values (`0`, `1`, $\to \infty$, singular inputs):
- **Default (SymPy / NumPy):**
  Execute a symbolic verification script (`python3 -c "import sympy as sp; ..."`).
- **Optional local math model:** If the `math-reasoning` extra (`extras/math-reasoning/`) is installed and its solver is available, use it as an additional cross-check of the analytical outputs and boundary conditions.

### Step 3: Synthesize Reference Implementation & Golden Unit Tests
1. Create a clean, self-contained reference module (e.g., `src/algorithms/<paper_slug>.py` or `.rs` / `.ts`) with docstrings citing the exact paper, equation numbers, and variable definitions.
2. Create a corresponding **Golden Unit Test Suite** (`tests/test_<paper_slug>.py`) asserting:
   - Exact numerical match against the analytical test vectors derived in Step 2 (`math.isclose(..., rel_tol=1e-6)`).
   - Monotonicity, conservation laws, or bounds specified by the paper's theorems.
   - Safe handling of degenerate/singular inputs (`NaN`, division by zero, empty arrays).
3. Run the test suite to confirm `0` errors before handing the module to the wider swarm.
