# cmd-orchestrator v1.0.1

Full standalone Hermes plugin. This is not a patch for v0.5.

## Slash commands

```text
/cmd-help
/cmd-status [--tasks|--json]
/cmd-mode [cheap|balanced|quality|fast]
/cmd-auto [off|review|on]
/cmd-plan <work>
/cmd-review
/cmd-run
/cmd-route <task>
/cmd-models
/cmd-learning
/cmd-checkpoint [note]
/cmd-resume [run_id]
/cmd-history
/cmd-rescue [reason]
/cmd-abort [reason]
```

## Automation modes

- `off`: orchestration only when explicitly requested.
- `review`: plan first; wait for `/cmd-run`.
- `on`: automatically encourage Hermes to orchestrate substantial work.

Recommended initial mode: `review`.

## Durable state

Source of truth:

`~/.hermes/state/cmd-orchestrator/orchestrator.sqlite3`

Learning data:

`~/.hermes/state/cmd-orchestrator/learning.sqlite3`

Human-readable project checkpoint, when working inside a repo:

`.ai/task_on_progress.md`

## Apple Intelligence rescue

`fm` is only a rescue layer. SQLite checkpointing happens first and does not depend on any model.

Manual rescue:

`/cmd-rescue`

## Clean install

Run self-test:

```bash
python3 selftest.py
```

Install while preserving old state:

```bash
python3 install.py
```

Install completely fresh, backing up then removing old state:

```bash
python3 install.py --clean-state
```

Backups are stored under:

`~/.hermes/plugin-backups/`

Never under `~/.hermes/plugins/`, preventing the duplicate-plugin bug from v0.5.

## Recommended workflow

```text
/cmd-auto review
/cmd-mode balanced
/cmd-plan <work>
/cmd-review
/cmd-run
/cmd-status --tasks
```

After confidence grows:

```text
/cmd-auto on
```
