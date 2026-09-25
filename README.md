# cmd-orchestrator v1.2.1

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


---

## CommandCode-native mode (v2 preview)

The repository now also contains a standalone runtime that does **not require Hermes**.

```text
request
  -> CommandCode planner
  -> fine-grained work_units
  -> dependency DAG
  -> per-unit model routing
  -> parallel CommandCode workers
  -> verification evidence
  -> durable run state / resume
```

The planner is deliberately instructed to split mixed-difficulty work into independently routable units (for example: interface design, easy helpers, difficult state machine, unit tests, regression tests, integration, documentation). Steps remain internal checklists so the system does not waste one model call per tiny step.

### Fish install

```fish
git clone https://github.com/phandinhdoc-spec/cmd-orchestrator.git
cd cmd-orchestrator
fish install-commandcode.fish
```

After this branch is merged to `main`:

```fish
cmd-orchestrator plan "Implement the requested feature with tests" --project (pwd)
cmd-orchestrator status
cmd-orchestrator run -j 3
```

The native state is stored under `~/.commandcode/cmd-orchestrator/`.

### CommandCode CLI compatibility

By default the adapter calls `commandcode --model <model>` and sends the worker prompt on stdin. If the installed CommandCode build uses another CLI syntax, set `COMMANDCODE_ARGS`. Supported placeholders are `{model}` and `{prompt_file}`.

Example:

```fish
set -Ux COMMANDCODE_ARGS '--model {model} --prompt-file {prompt_file}'
```

Routing aliases are intentionally editable rather than hard-coded to one subscription catalog. Set `CMD_MODEL_ROUTES` to a JSON file to replace the default cheap/balanced/strong/review mappings. Set `CMD_PLANNER_MODEL` to choose the planning model.

This native runtime is separate from the existing Hermes plugin so current Hermes users are not broken during migration.
