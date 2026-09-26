from __future__ import annotations
from datetime import datetime
from pathlib import Path


def _stamp():
    return datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")


def _display_time():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _next_sequence(plan_dir: Path) -> int:
    plan_dir.mkdir(parents=True, exist_ok=True)
    nums=[]
    for p in plan_dir.glob("*_plan.md"):
        try: nums.append(int(p.name.split("_",1)[0]))
        except (ValueError, IndexError): pass
    return max(nums, default=0)+1


def write_plan_markdown(project, run_id, plan, tree):
    """Persist a detailed, human-editable Markdown plan beside the project."""
    root=Path(project).expanduser().resolve() if project else Path.cwd().resolve()
    plan_dir=root/".ai"/"cmd-plans"
    seq=_next_sequence(plan_dir)
    path=plan_dir/f"{seq:04d}_{_stamp()}_plan.md"
    created=_display_time()
    lines=[
        f"# PLAN {seq:04d} — {plan.get('summary') or run_id}",
        "",
        f"> Created: {created}",
        f"> Updated: {created}",
        f"> Run ID: {run_id}",
        "> Status: REVIEW",
        "> Source of truth: human-editable Markdown; reread before approve/resume.",
        "",
        "## Objective","",str(plan.get("summary") or ""),"",
    ]
    for ti,task in enumerate(tree,1):
        mark="x" if task.get("status")=="DONE" else " "
        lines += [
            f"## {ti}. [{mark}] {task.get('task_id')} — {task.get('title') or ''}","",
            f"**Depends on:** {', '.join(task.get('dependencies') or []) or 'none'}  ",
            f"**Class / risk:** {task.get('task_class') or 'general'} / {task.get('risk') or 'medium'}","",
            "### Planner comment","",
            str(task.get("description") or "Planner must explain why this task exists, assumptions, risks, reuse constraints, and handoff expectations."),"",
        ]
        for ui,u in enumerate(task.get("work_units") or [],1):
            umark="x" if u.get("status") in ("DONE","SKIPPED") else " "
            lines += [
                f"{ui}. - [{umark}] **{u.get('unit_id')} — {u.get('title') or ''}**",
                f"   - **Depends on:** {', '.join(u.get('dependencies') or []) or 'none'}",
                f"   - **Agent/model:** {u.get('provider') or 'auto'} / {u.get('model') or 'auto'}",
                f"   - **Reason:** {u.get('reasoning') or 'Planner must document the routing reason.'}",
                f"   - **Verification:** {u.get('verification') or 'Planner must define acceptance evidence.'}",
                "   - **Detailed comment:**",
                f"     {u.get('description') or 'Explain WHY, assumptions, risks, library/API reuse decision, allowed write scope, and what must not change.'}",
                "   - **Checklist:**",
            ]
            for s in u.get("steps") or []:
                smark="x" if s.get("status")=="DONE" else " "
                detail=f" — {s.get('description')}" if s.get("description") else ""
                lines.append(f"     - [{smark}] {s.get('step_id')} {s.get('title') or ''}{detail}")
            lines += ["   - **Acceptance / verification:**", "     - [ ] Verification evidence recorded before DONE.",""]
    lines += [
        "## Human editing contract","",
        "- [ ] Review task order, dependencies, routes, comments, and acceptance criteria.",
        "- [ ] Edit this Markdown directly when needed.",
        "- [ ] CMD/Hermes rereads this file before approve/resume and reconciles valid edits.",
        "- [ ] A checked box alone never proves completion; verification evidence is required.",
        "",
        "<!-- CMD: Preserve planner comments and human edits during automatic status updates. -->","",
    ]
    path.write_text("\n".join(lines),encoding="utf-8")
    return str(path)
