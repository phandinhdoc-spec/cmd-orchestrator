# cmd-orchestrator v1.1.0

Standalone multi-model orchestration plugin for Hermes.

## New in v1.1

The operator can see the complete task/model routing plan before execution and override the model for any task that has not started. /cmd-status is detailed by default. /cmd-model and /cmd-models show the provider/model catalog visible to the current Hermes installation instead of only cmd-orchestrator logical tiers.

## Recommended review workflow

    /cmd-auto review
    /cmd-mode balanced
    /cmd-plan <work>

At this point cmd shows TASK / STATUS / PROVIDER / MODEL / routing reason.

Optional overrides:

    /cmd-model T2 commandcode <exact-model-id>
    /cmd-model T3 auto
    /cmd-review
    /cmd-run
    /cmd-status

A route can be changed while a run is active only while that task is READY or PENDING. Tasks already RUNNING or terminal are protected. Hermes is instructed to re-read the saved route immediately before each task, so an override made before that task begins is honored.

## Slash commands

    /cmd-help
    /cmd-status [--json]
    /cmd-mode [cheap|balanced|quality|fast]
    /cmd-auto [off|review|on]
    /cmd-plan <work>
    /cmd-review
    /cmd-run
    /cmd-route <task>
    /cmd-model
    /cmd-model <TASK_ID> <provider> <model>
    /cmd-model <TASK_ID> auto
    /cmd-models
    /cmd-learning
    /cmd-checkpoint [note]
    /cmd-resume [run_id]
    /cmd-history
    /cmd-rescue [reason]
    /cmd-abort [reason]

## Model catalog

/cmd-model with no arguments and /cmd-models are aliases for the Hermes-visible catalog. Discovery uses Hermes configuration, its authenticated-provider helper when available, models.dev catalog, and provider fallback declarations. Credentials are never returned.

## Automation modes

- off: orchestration only when explicitly requested.
- review: plan and route first; user can edit routes; wait for /cmd-run.
- on: automatically orchestrate substantial work.

Recommended initial mode: review.

## Durable state

Source of truth: ~/.hermes/state/cmd-orchestrator/orchestrator.sqlite3

Learning data: ~/.hermes/state/cmd-orchestrator/learning.sqlite3

Human-readable project checkpoint: .ai/task_on_progress.md

## Apple Intelligence rescue

fm is only a rescue layer. SQLite checkpointing happens first and does not depend on any model.

Manual rescue: /cmd-rescue

## Clean install

    python3 selftest.py
    python3 install.py

Fresh state, with backup:

    python3 install.py --clean-state

Backups are stored under ~/.hermes/plugin-backups/, never under ~/.hermes/plugins/.
