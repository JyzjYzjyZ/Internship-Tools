---
name: ai-web-coding-documentation
version: 1.0.0
description: Maintain a durable, low-noise documentation system for AI-assisted Web Coding projects. Use when analyzing an existing codebase, planning risky or multi-file changes, recording architecture, preserving verified debugging knowledge, documenting semantic code anchors, recording architectural decisions, validating implementation, or explaining complex technical work to a user. The system uses docs/plan, docs/frames, docs/exp, docs/memory, docs/var, docs/evidence, docs/decision, and docs/forUser, with an optional root AGENTS.md as the always-on router.
---

# AI Web Coding Documentation Protocol

## Purpose

This skill treats project documentation as an engineering context system for coding agents, not as a passive project diary.

The goal is to let a future AI agent answer five questions with minimal context loading:

1. What is this project now?
2. Where is the relevant code and how is it semantically located?
3. What has already been verified, and what is still only a hypothesis?
4. Why were important architectural choices made?
5. What is the current task, its boundaries, and how will completion be verified?

The system should preserve durable knowledge without turning the repository into a large pile of notes.

## Core doctrine

### 1. Documentation is layered context

Do not load every document for every task.

Start from the project's agent-facing router when one exists, then load only the smallest task-specific context needed.

Preferred order:

```text
AGENTS.md (if present)
        ↓
docs/memory/
        ↓
relevant frames / var / decision / evidence / exp
        ↓
current plan
        ↓
code inspection and implementation
        ↓
verification
        ↓
documentation update when durable knowledge changed
```

`docs/memory/` is an index/router only. Despite its name, it is not the place for project memory, rules, preferences, or execution notes.

### 2. Separate current truth, evidence, decisions, experience, and intent

Use these meanings strictly:

| Location | Answers | Time orientation |
|---|---|---|
| `docs/frames/` | What the system currently is | current |
| `docs/var/` | Where/how key code is semantically identified | current |
| `docs/evidence/` | What was actually measured or verified | past/current evidence |
| `docs/decision/` | Why an important choice was made | durable |
| `docs/exp/` | What was learned and can be reused | durable experience |
| `docs/plan/` | What we are going to change now | future |
| `docs/memory/` | Where relevant documents are | navigation |
| `docs/forUser/` | How to explain technical results plainly | presentation |

Do not collapse these layers into one generic `notes/` folder.

### 3. Do not document everything

Documentation has a maintenance cost.

Create or update a document when at least one of these is true:

- the knowledge is likely to matter in a future session;
- the behavior is architecturally significant;
- an experiment changed the understanding of the system;
- a failure mode is likely to recur;
- a decision would otherwise be silently reversed later;
- a semantic code location is important enough that future agents need a stable reference;
- the task is large enough that a written plan and verification record reduce execution risk.

Do not create durable docs for trivial style edits, obvious one-line fixes, or transient scratch work unless the user explicitly requests it.

## Directory contract

### `docs/plan/`

Purpose: the current task's executable plan.

A plan should define:

- objective;
- scope;
- files/components in scope;
- files/components explicitly out of scope;
- assumptions;
- implementation sequence;
- dependencies;
- risks;
- validation gates;
- rollback or preservation constraints when relevant.

For complex work, the plan should be produced only after reading the current architecture and relevant evidence.

A plan is not the permanent architecture document. Once implementation reveals durable facts, move those facts into the appropriate long-lived documents.

Recommended status markers:

```text
DRAFT
APPROVED
IN_PROGRESS
VERIFIED
ABANDONED
SUPERSEDED
```

### `docs/frames/`

Purpose: current architecture and system structure.

Describe:

- major modules and responsibilities;
- data flow;
- render/update lifecycle;
- state machines;
- subsystem boundaries;
- important dependencies;
- invariants and constraints;
- ownership of state and side effects;
- critical interaction paths.

Write what the system is, not what you wish it were.

Prefer behavior and relationships over source listing.

Bad:

```text
showSplit20.html lines 1847-1912 contain the ground logic.
```

Good:

```text
showSplit20.html contains the ground rendering initialization that creates the
GroundBase material and connects it to the ground render path; the contact
shadow layer is attached through a separate overlay path.
```

### `docs/var/`

Purpose: semantic anchor registry for important code locations.

This is not merely a variable list. It can contain:

- variables;
- constants;
- functions;
- objects/groups;
- DOM nodes;
- materials;
- shaders;
- render targets;
- state fields;
- lifecycle hooks;
- event handlers;
- configuration objects;
- unique structural code blocks.

#### Semantic anchor rule

Never make a source-code line number the primary long-term locator.

Use a stable semantic identity instead:

```text
file + symbol name
file + function/object role
file + structural relationship
file + distinctive code characteristic
```

Line numbers may be included as temporary debugging aids, but they must not be the only reference for durable documentation.

#### Anchor quality

A good anchor should survive harmless insertions, formatting changes, and nearby refactors.

An anchor should contain enough information for another agent to find the correct code without relying on an old line number.

Preferred pattern:

```markdown
## Anchor: <name>

- File: <project-relative path>
- Kind: function | object | state | shader | material | DOM | structural block
- Role: <what it owns or does>
- Identifying characteristics: <distinctive names / call relationship / code behavior>
- Inputs: <important inputs>
- Outputs/effects: <important effects>
- Related anchors: <links>
- Stability note: <why this reference is durable>
```

### `docs/evidence/`

Purpose: preserve evidence that supports important technical conclusions.

Evidence can include:

- probe scripts;
- logs;
- regression results;
- measured timings;
- counts;
- before/after observations;
- screenshots or visual checkpoints;
- benchmark notes;
- reproducible reproduction steps.

Rules:

- distinguish measured results from inference;
- include the test conditions needed to interpret the result;
- timestamp results when they can become stale;
- avoid dumping giant raw transcripts into the repository;
- keep the smallest artifact that can reproduce or substantiate the conclusion.

Use explicit confidence language when needed:

```text
FACT        directly observed or mechanically verified
EVIDENCE    supporting observation/result
HYPOTHESIS  plausible but not verified
UNKNOWN     not yet established
```

Never silently upgrade `HYPOTHESIS` to `FACT`.

### `docs/exp/`

Purpose: durable experience extracted from real implementation, debugging, experiments, or failed approaches.

An experience record should prefer:

```text
Phenomenon
Experiment / investigation
Observed result
Root cause (if established)
Rejected hypotheses
Final lesson
Reuse guidance
```

Do not use `exp/` as a chronological diary.

Good `exp/` records answer:

> If a future agent sees this problem again, what should it know before trying random fixes?

### `docs/decision/`

Purpose: preserve architecturally significant decisions so they are not silently reversed.

Use one decision per record.

Recommended structure:

```markdown
# <Decision Title>

- Status: proposed | accepted | rejected | deprecated | superseded
- Date: YYYY-MM-DD

## Context

<problem, constraints, competing forces>

## Decision

<chosen direction>

## Consequences

### Positive
<what becomes easier or safer>

### Negative
<what becomes harder or more constrained>

## Alternatives Considered

<important alternatives and why they were not selected>

## Evidence / References

<links to evidence, frames, experiments, or code anchors>
```

A decision record is warranted when the decision:

- affects architecture or subsystem boundaries;
- affects an external interface;
- affects an important quality attribute;
- is risky or expensive to reverse;
- involved meaningful trade-offs;
- must be understood by future contributors.

Do not create an ADR-style record for tiny temporary choices.

Once an accepted decision is replaced, prefer a new decision record plus explicit supersession rather than silently rewriting history.

### `docs/memory/`

Purpose: navigation only.

It should contain an index such as:

```markdown
# Documentation Index

## Architecture
- `frames/...` — current rendering architecture
- `frames/...` — camera state architecture

## Code Anchors
- `var/...` — key camera functions and state

## Evidence
- `evidence/...` — regression and probe results

## Decisions
- `decision/...` — accepted architectural decisions

## Experience
- `exp/...` — reusable debugging knowledge

## Current Work
- `plan/...` — active implementation plan

## User Explanations
- `forUser/...` — long-form plain-language explanations
```

Do not store execution rules, preferences, temporary remarks, or project facts here.

The index must point agents toward the correct source; it must not become a second knowledge base.

### `docs/forUser/`

Purpose: explain long or difficult technical results in maximum plain language.

Rules:

- lead with the conclusion;
- explain the cause in ordinary language;
- distinguish what is proven from what is suspected;
- explain why the issue matters;
- explain what changed and what did not change;
- avoid unnecessary jargon;
- do not introduce facts that do not exist in the engineering records.

`forUser/` is a presentation layer, not the source of technical truth.

## Root `AGENTS.md` integration

When `AGENTS.md` exists, treat it as the always-on project router and stable execution rule set.

It should remain short enough to be reliably loaded. It should tell the agent:

- the documentation system exists;
- where the index lives;
- what to read for common task types;
- which sources own which kinds of truth;
- hard project constraints;
- required verification behavior;
- what must never be committed or exposed.

Do not turn `AGENTS.md` into a project encyclopedia. Put durable detail in the appropriate `docs/` layer.

If no `AGENTS.md` exists, the skill may still operate from `docs/memory/` and the repository's existing agent rules.

## Source-of-truth ownership

When multiple documents speak about the same subject, ownership must be explicit.

Recommended ownership:

```text
Stable execution rules      → AGENTS.md
Current architecture        → docs/frames/
Current code identities     → docs/var/
Observed measurements       → docs/evidence/
Durable design rationale    → docs/decision/
Reusable lessons            → docs/exp/
Current task intent         → docs/plan/
Navigation                  → docs/memory/
Human-facing explanation    → docs/forUser/
```

If two documents conflict:

1. inspect the current code;
2. inspect the newest relevant evidence;
3. determine whether the document is stale, wrong, or intentionally describing future intent;
4. update the owning document rather than spreading the contradiction.

Do not resolve document conflicts by blindly choosing the longest or newest text.

## Task routing

Before acting on a non-trivial Web Coding task, classify the task.

### Bug / regression

Read:

```text
AGENTS.md
memory index
relevant frames
relevant var anchors
evidence from the failing behavior
relevant exp / decisions
```

Then:

```text
reproduce → inspect → form hypotheses → test → identify cause → plan fix → implement → verify → record durable result
```

Keep diagnosis, repair, and verification conceptually separate.

A fix is not considered verified merely because the code changed or the symptom disappeared once.

### Architecture change / merge

Read:

```text
AGENTS.md
memory index
relevant frames
relevant var
relevant decisions
evidence / regressions
```

Then create or update a plan containing explicit in-scope and out-of-scope boundaries.

For risky merges, document:

- source branch behavior;
- target branch behavior;
- exact semantic responsibilities being imported;
- preserved invariants;
- known incompatibilities;
- validation matrix.

### New feature

For a substantial feature, define the intended behavior before implementation.

Use the sequence:

```text
Intent / requirements
    ↓
Research / existing-code reconnaissance
    ↓
Plan
    ↓
Task breakdown
    ↓
Implementation
    ↓
Validation
    ↓
Convergence review
```

The plan must not be generated from the user request alone when important architecture or dependency questions remain unknown.

### Small edit

Do not create a full documentation ceremony for a trivial change.

Use the smallest context sufficient to make the edit safely and update durable documentation only when the change alters a reusable fact, architecture, constraint, or known behavior.

## Progressive disclosure and context efficiency

Do not blindly read every markdown file.

Prefer:

```text
index → relevant summary → specific record → source code/evidence
```

Use stable identifiers for traceability:

```text
FR-001
SC-001
US-01
AC-02
TASK-003
ANCHOR: cameraState
EVIDENCE: focus-handoff-2026-10-01
DECISION: preserve-hero-framing
```

Stable identifiers make cross-document analysis less dependent on prose matching.

Avoid repeatedly copying the same paragraph into multiple files.

Link to the authoritative record instead.

## Planning rules

A high-quality plan must be reviewable before implementation.

At minimum it should answer:

```text
What is changing?
Why is it changing?
Where is it changing?
What must not change?
What assumptions remain?
What evidence supports the design?
How will success be measured?
```

For unresolved technical questions:

- mark them explicitly;
- research before implementation when the answer affects architecture or scope;
- do not hide uncertainty under confident prose.

## Validation and convergence

After implementation, verify the actual code against the intended plan and requirements.

Check for:

- missing work;
- partial work;
- contradictions;
- unrequested changes;
- terminology drift;
- stale assumptions;
- regressions in preserved behavior;
- insufficient test coverage.

Completion claims are not evidence.

Prefer measurable validation such as:

```text
0 unexpected jumps
68/68 tests passed
251/251 valid assets
2.2 ms steady-state render cost
0 stale-pending transitions
```

Do not invent a metric simply to make a plan look complete.

If an implementation passes the original task but reveals a durable architectural lesson, record the lesson in `exp/`, `frames/`, `decision/`, or `evidence/` as appropriate.

## Documentation update rules

After significant work, determine what actually changed in project knowledge.

### Update `frames/` when

- architecture changed;
- ownership changed;
- lifecycle/state flow changed;
- an invariant or dependency changed.

### Update `var/` when

- an important semantic anchor was created, removed, renamed, or structurally changed.

### Update `evidence/` when

- new measurements or regression results support an important claim.

### Update `exp/` when

- a reusable lesson was learned from a real experiment or debugging episode.

### Update `decision/` when

- an architecturally significant choice was accepted, rejected, or superseded.

### Update `plan/` when

- the active task's scope, sequence, or validation criteria changed.

### Update `memory/` when

- document locations or navigation meaning changed.

### Update `forUser/` when

- the user needs a durable plain-language explanation that will be reused.

Do not update every document after every coding session.

## Anti-patterns

Never:

- turn documentation into a development diary;
- duplicate the same fact across many files;
- use line numbers as the only durable code locator;
- write hypotheses as established causes;
- treat an old plan as current architecture;
- treat an index as a source of truth;
- use `forUser/` as engineering truth;
- create a decision record for every trivial implementation detail;
- dump complete chat transcripts into the repository;
- preserve stale documentation merely because it already exists;
- claim verification without evidence;
- expand the documentation system automatically just because the project became more complex.

## Required behavior for agents using this skill

When this skill is active:

1. For a non-trivial task, inspect the documentation router before making architectural assumptions.
2. Load only task-relevant context.
3. Prefer semantic anchors over line numbers in durable documentation.
4. Explicitly distinguish fact, evidence, hypothesis, decision, and plan.
5. Write a plan before risky implementation when the user has not already provided one.
6. Keep diagnosis, implementation, and verification distinct.
7. Verify against preserved behavior, not only new behavior.
8. Update only the documentation layers whose durable meaning changed.
9. When documents conflict, reconcile them against current code and evidence.
10. Never silently discard an existing architectural constraint because it is inconvenient.
11. When a major decision is replaced, preserve the historical rationale through explicit supersession.
12. Keep context small enough that a future agent can actually use it.

## Recommended document lifecycle

```text
DISCOVER
  ↓
ROUTE
  ↓
READ MINIMUM CONTEXT
  ↓
RESEARCH / REPRODUCE
  ↓
PLAN
  ↓
IMPLEMENT
  ↓
VERIFY
  ↓
CONVERGE
  ↓
EXTRACT DURABLE KNOWLEDGE
  ↓
UPDATE ONLY THE OWNING DOCUMENTS
```

## Research basis

This protocol is an original synthesis for AI-assisted Web Coding. It was informed by the following public GitHub projects and practices, but it does not reproduce their files verbatim:

- GitHub Spec Kit — structured specify/plan/tasks/implement/converge workflow, consistency analysis, progressive disclosure, and convergence checks.
- Cline prompts — Memory Bank hierarchy, active context, progress tracking, and cross-session documentation.
- `ohgenius1997/project-memory` — AGENTS-first context routing, minimal always-on context, stable-vs-dynamic memory ownership, and documentation health/compaction ideas.
- `architecture-decision-record/architecture-decision-record` — one-decision-per-record, context/decision/consequences, explicit status, timestamping, and supersession.
- `wmeints/context-engineering` — layered context, research-driven plans, and self-validating workflows.
- `bonigarcia/context-engineering` — broader context-engineering model covering instructions, external knowledge, memory/state, context management, evaluation/observability, and governance.

The key adaptation for Web Coding is the explicit `var/` semantic-anchor layer and the `evidence/` layer. These are treated as first-class project context because browser/Three.js work often involves large mutable files, generated or visually tuned code, runtime probes, render timing, state-machine behavior, and repeated branch merges where line-number references become brittle.

## Reference links

- https://github.com/github/spec-kit
- https://github.com/cline/prompts
- https://github.com/ohgenius1997/project-memory
- https://github.com/architecture-decision-record/architecture-decision-record
- https://github.com/wmeints/context-engineering
- https://github.com/bonigarcia/context-engineering
