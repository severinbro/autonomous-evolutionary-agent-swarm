# <Feature or Product Name>

*   **Author:** <name from `git config user.name`>
*   **Status:** Draft
*   **Date:** <YYYY-MM-DD>

--------------------------------------------------------------------------------

## Overview

<!-- What this builds, for whom, and why, in a few sentences a newcomer can follow. -->

## The Problem

<!-- The problem and its evidence: what fails or is missing today, and how we know. -->

## Goals

<!-- Specific, checkable outcomes. Each one should be verifiable by a command or an observation. -->

*   **G1 — <name>.** <outcome>

## Non-Goals

<!-- What is deliberately out of scope, so the implementer does not add it (YAGNI). -->

*   <non-goal>

## Resolved Decisions

<!-- Key scope, architectural, and edge-case decisions settled with the user via the harness polling tool (`ask_question` / `AskUserQuestion` / `request_user_input`) before implementation. Never place open questions here. -->

*   **D1 — <topic>:** <chosen option and concise rationale>.

## Critical User Journeys (CUJs)

### CUJ 1: <journey title>

*   **Given**: <starting state>
*   **When**: <action or event>
*   **Then**: <observable result>

## Technical Plan (Architecture)

<!-- Components, data flow, interfaces, and how this fits the existing code. Prefer stdlib and existing modules over new abstractions. -->

## Alternatives Considered

### Alternative A: <title>

*   **Pros**: <benefits>
*   **Cons**: <drawbacks>
*   **Reason for Rejection**: Rejected by author: <the deciding technical or scope reason>

--------------------------------------------------------------------------------

## Risks

<!-- Failure modes, security and data risks, and costs, each with its mitigation or an explicit acceptance. -->

## Non-Functional Requirements

<!-- Performance, cost (including LLM tokens), compatibility, rollout and rollback. Write "None critical." if so. -->

--------------------------------------------------------------------------------

### Additional Resources

<!-- Documents, issues, papers or code consulted. Omit if none. -->

### Future Improvements

<!-- Ideas deliberately left for later, plus anything intentionally skipped or not checked. Omit if none. -->

--------------------------------------------------------------------------------

## Detailed Implementation Plan

<!--
`goal_loop.py --import-design` reads only the `### Goal` block and the `### Task <ID>: <title>` blocks below,
and rejects any non-fenced `Open Questions` heading or `[?]` marker anywhere in the document.
Decompose into vertical slices ("tracer bullets"): each task wires real behavior + a failing-first test (`Verification`).
Fields are bullets at column 0. Required: Files (each path tagged Create/Modify/Delete), Depends on, Changes,
Verification (a backticked command that fails without the change). Optional: Outcome, Review focus, Called by, Symbols.
Prefix task IDs with a short name for this design (DEMO-1, DEMO-2, ...) so they never collide with another design's.
Replace the sample task below.
-->

### Goal

*   **Goal:** <one sentence: what the finished plan delivers>
*   **Outcome:** `python3 -m unittest discover -s tests`

### Task DEMO-1: Add a greeting function

*   **Files:** `src/greeting.py` (Create), `tests/test_greeting.py` (Create)
*   **Depends on:** none
*   **Changes:** Add `greet(name: str) -> str` returning `"Hello, <name>!"`. An empty or whitespace-only name raises `ValueError("name must not be empty")`.
*   **Verification:** `python3 -m unittest discover -s tests -p "test_greeting.py"`
*   **Review focus:**
    1.  `greet("Ada")` returns `"Hello, Ada!"`.
    2.  `greet("")` and `greet("   ")` raise `ValueError`.
