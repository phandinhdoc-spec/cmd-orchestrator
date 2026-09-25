# cmd-orchestrator v1.3.0

`cmd-orchestrator` is a **control plane for Hermes**, not a second orchestrator.

Hermes remains responsible for understanding the job, planning, dependencies, parallelism, worker/model selection, and execution. CMD makes those decisions visible, lets the human intervene, persists execution state, and turns reflection into editable learning.

## Core principle

```text
Hermes = orchestrator
CMD    = transparency + control + durable state + teachable learning
```

The preferred representation is DSL-like and code-shaped so plans are easy to inspect and edit.

## Default flow

```text
user_prompt
    |
    v
Hermes decides DIRECT vs ORCHESTRATED
    |
    +-- DIRECT ------------------------------> execute directly
    |                                          shell/API first; Computer Use for GUI
    |
    `-- ORCHESTRATED
          |
          v
       Grill Me
          |
          v
prompt_review {
  original = """FULL original prompt"""
  grilled  = """FULL Grill Me prompt"""
}
          |
          +-- original
          +-- grilled
          `-- edited
          |
          v
       Hermes plan
          |
          v
plan {
  task T1 {
    work_unit W1.1 {
      route = "provider/model"
      step S1.1.1 {}
      step S1.1.2 {}
    }
  }
}
          |
          v
human review / edit / model override
          |
          v
         RUN
          |
          v
Hermes reflection -> CMD learning review -> human teaches/corrects Hermes
```

## Plan resolution: Task -> Work Unit -> Step

v1.2 deliberately separates plan detail from execution granularity.

- **Task**: a meaningful phase such as design, implementation, test, documentation.
- **Work Unit**: the smallest independently routable/executable unit. Model selection happens here by default.
- **Step**: a detailed checklist inside a work unit. A step does **not** automatically become another agent call.

This allows Hermes to expose mixed difficulty inside one task. Example: easy helper functions can use a cheap model while a difficult algorithm/state machine can use a stronger model.

The rule is:

```text
Plan deeply. Execute efficiently.
```

CMD validates whether a Hermes plan is too coarse, but CMD does not invent the missing plan. It asks Hermes to expand it.

## v1.3 execution policy: library-first + atomic multi-agent

For code, CMD now treats an independently changeable **function/method as the default atomic work unit**. Before any custom implementation, Hermes must create/perform library discovery: inspect project dependencies, standard/framework APIs, official packages, then suitable maintained third-party libraries. Reimplementing functionality already supplied by a suitable library is a hard planning failure.

```text
library discovery -> freeze interfaces -> atomic function work units -> READY DAG frontier
                                                        |-> worker A
                                                        |-> worker B
                                                        |-> worker C
                                                   -> integration/regression
```

Independent READY units should be assigned to separate workers concurrently up to `max_parallel` (default 3). Units with overlapping write scopes must not run concurrently. Workers do not recursively spawn/orchestrate other workers: Hermes remains the single parent orchestrator and performs final integration.

Tiny getters/setters/generated wrappers may be grouped only when coordination cost would exceed the work itself. Custom code must have either a dependency on a `library_discovery` unit or explicit `library_evidence` showing why reuse is insufficient.

## Prompt review

For substantial work, Grill Me / `grill-tab` should run first when available. CMD must show the **full original prompt and full grilled prompt**. Grill output never silently replaces user intent.

```text
/cmd-prompt
/cmd-prompt original
/cmd-prompt grilled
/cmd-prompt edit <full edited prompt>
```

CMD stores `original_prompt`, `grilled_prompt`, and `selected_prompt` separately.

## Task review and human intervention

Hermes creates the plan and chooses default provider/model routes. CMD renders that plan in a DSL-like form.

```text
/cmd-review
/cmd-edit W2.1 title="Easy helpers" risk=low verification="unit tests"
/cmd-model W2.1 commandcode <exact-model-id>
/cmd-model W2.1 auto
/cmd-run
```

`/cmd-model ... auto` restores **Hermes' original route**, not a route invented by CMD.

Only not-yet-started work is editable:

```text
PENDING / READY / WAITING -> editable
RUNNING                   -> locked
DONE / FAILED / SKIPPED   -> locked
```

## Simple commands

CMD does not force every request through Grill and plan review. Hermes first decides whether the request is simple enough for direct execution.

For direct work, prefer the most reliable direct mechanism:

1. shell/tool/API when available;
2. Computer Use when the task genuinely requires GUI interaction.

Examples: `git status`, renaming a file, running tests, or reading a known file should normally be direct. GUI navigation may use Computer Use.

## Learning: Hermes learns first, CMD fills gaps

After a run, Hermes should reflect and submit evidence-based learning. CMD stores that reflection as human-reviewable entries.

CMD distinguishes:

```text
OBSERVATION -> LESSON -> RULE
```

Typical states:

```text
CANDIDATE -> APPROVED -> ACTIVE
             |            |
             +-> EDITED   +-> DISABLED
REJECTED / ARCHIVED
```

If Hermes finishes a run without recording reflection, CMD creates only a low-confidence operational **observation**. It does not silently promote one event into a rule.

### Teach Hermes

```text
/cmd-learn
/cmd-learn add <rule>
/cmd-learn edit L0003 <corrected lesson>
/cmd-learn approve L0003
/cmd-learn activate L0003
/cmd-learn disable L0003
/cmd-learn reject L0003
/cmd-learn delete L0003
```

Learning authority is intentionally ordered:

```text
user-taught ACTIVE rule
    > user-approved Hermes lesson
    > unapproved Hermes candidate
    > CMD fallback observation
```

Before future substantial work, Hermes can retrieve ACTIVE/APPROVED lessons as context. Those lessons inform Hermes; they do not replace Hermes planning authority.

## Commands

```text
/cmd-status [--json]
/cmd-prompt [original|grilled|edit <prompt>]
/cmd-plan <work>                     # manual planning request; normally automatic
/cmd-review
/cmd-edit <ID> field=value ...
/cmd-run
/cmd-model
/cmd-model <W#.#> <provider> <model>
/cmd-model <W#.#> auto
/cmd-models
/cmd-learn [action ...]
/cmd-learning                       # alias
/cmd-clean [select IDs...|project|all] [--deep] [--learning]
/cmd-checkpoint [note]
/cmd-resume [run_id]
/cmd-history
/cmd-rescue [reason]
/cmd-abort [reason]
/cmd-auto [off|review|on]
/cmd-mode [cheap|balanced|quality|fast]  # compatibility hint only
/cmd-help
```


## Cleanup

`/cmd-clean` only targets artifacts known to be generated by CMD. Project files require a CMD marker before deletion; plugin source files are never touched.

```text
/cmd-clean
/cmd-clean select P1 P2
/cmd-clean project
/cmd-clean project --deep
/cmd-clean all
/cmd-clean all --deep
/cmd-clean all --deep --learning
```

Three cleanup modes:

- **select**: preview the generated-file list and delete only IDs chosen by the user.
- **project**: clean CMD artifacts belonging to the current project. `--deep` also removes matching CMD run snapshots.
- **all**: clean CMD artifacts accumulated across runs. `--deep` also resets CMD runtime state.

Learning and settings are protected by default. Deleting learned memory requires the explicit destructive form `/cmd-clean all --deep --learning`.

## Durable state

```text
~/.hermes/state/cmd-orchestrator/orchestrator.sqlite3
~/.hermes/state/cmd-orchestrator/learning.sqlite3
~/.hermes/state/cmd-orchestrator/runs/
```

When working inside a project, CMD also keeps a human-readable checkpoint at:

```text
.ai/task_on_progress.md
```

## Model ownership

Hermes is the default routing authority in v1.2. CMD stores both the original Hermes route and any operator override at work-unit level.

`/cmd-model` and `/cmd-models` show the model catalog visible to the installed Hermes environment when the relevant Hermes APIs are available.

## Apple Intelligence rescue

`fm` remains an emergency local rescue layer. Durable SQLite checkpointing happens first and does not depend on a model.

```text
/cmd-rescue
```

## Install / test

```bash
python3 selftest.py
python3 install.py
hermes plugins doctor ~/.hermes/plugins/cmd-orchestrator --ci
```

For a clean state with backup:

```bash
python3 install.py --clean-state
```

Backups remain under `~/.hermes/plugin-backups/`.
