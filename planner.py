from __future__ import annotations

GENERIC_TITLES = {
    "implement", "implementation", "code", "write code", "triển khai", "viết code",
    "test", "kiểm thử", "document", "docs", "soạn tài liệu", "làm tài liệu"
}

def hermes_plan_contract():
    """Contract shown to Hermes. CMD validates resolution but does not invent the plan."""
    return {
        "owner": "hermes",
        "resolution": "task/work_unit/step",
        "rules": [
            "Hermes owns planning, dependency analysis, parallelism, and default model selection.",
            "Make the plan as detailed as necessary to expose mixed difficulty inside a task.",
            "A work_unit is the smallest independently routable/executable unit; do not create one agent call per step.",
            "Steps explain the work inside a unit and are not routing boundaries by default.",
            "Put provider/model/reasoning on each work_unit when Hermes can choose them.",
            "Separate design, implementation, verification, and final integration when materially different.",
            "For code, split easy mechanical functions from difficult algorithms/state/architecture when useful.",
            "For documents, split structure, simple drafting, difficult reasoning, exercises/answers, and verification when useful.",
        ],
        "shape": {
            "summary": "string",
            "tasks": [{
                "id": "T1",
                "title": "string",
                "description": "string",
                "dependencies": [],
                "work_units": [{
                    "id": "W1.1",
                    "title": "string",
                    "description": "string",
                    "dependencies": [],
                    "task_class": "string",
                    "risk": "low|medium|high",
                    "provider": "Hermes-selected provider",
                    "model": "Hermes-selected model",
                    "reasoning": "why Hermes chose this route",
                    "verification": "acceptance evidence",
                    "steps": [{"id": "S1.1.1", "title": "string", "description": "string"}],
                }],
            }],
        },
    }

def normalize_plan(plan):
    plan = plan if isinstance(plan, dict) else {}
    out = {"summary": str(plan.get("summary") or ""), "tasks": []}
    issues = []
    for ti, raw_task in enumerate(plan.get("tasks") or [], 1):
        task = raw_task if isinstance(raw_task, dict) else {}
        tid = str(task.get("id") or f"T{ti}")
        units = task.get("work_units") or []
        normalized_units = []
        if not units:
            issues.append(f"{tid}: no work_units; Hermes should expand this task before execution")
        for ui, raw_unit in enumerate(units, 1):
            unit = raw_unit if isinstance(raw_unit, dict) else {}
            uid = str(unit.get("id") or f"W{ti}.{ui}")
            steps = []
            for si, raw_step in enumerate(unit.get("steps") or [], 1):
                step = raw_step if isinstance(raw_step, dict) else {"title": str(raw_step)}
                steps.append({
                    "id": str(step.get("id") or f"S{ti}.{ui}.{si}"),
                    "title": str(step.get("title") or step.get("description") or "step"),
                    "description": str(step.get("description") or ""),
                })
            title = str(unit.get("title") or unit.get("description") or uid)
            if title.strip().lower() in GENERIC_TITLES and len(steps) < 2:
                issues.append(f"{uid}: generic/coarse work_unit; expand mixed-difficulty work if present")
            normalized_units.append({
                "id": uid,
                "title": title,
                "description": str(unit.get("description") or ""),
                "dependencies": list(unit.get("dependencies") or []),
                "task_class": str(unit.get("task_class") or "general"),
                "risk": str(unit.get("risk") or "medium"),
                "provider": str(unit.get("provider") or ""),
                "model": str(unit.get("model") or ""),
                "reasoning": str(unit.get("reasoning") or "Hermes route"),
                "verification": str(unit.get("verification") or ""),
                "steps": steps,
            })
        out["tasks"].append({
            "id": tid,
            "title": str(task.get("title") or tid),
            "description": str(task.get("description") or ""),
            "dependencies": list(task.get("dependencies") or []),
            "task_class": str(task.get("task_class") or "general"),
            "risk": str(task.get("risk") or "medium"),
            "verification": str(task.get("verification") or ""),
            "work_units": normalized_units,
        })
    if not out["tasks"]:
        issues.append("plan has no tasks")
    unit_count = sum(len(t["work_units"]) for t in out["tasks"])
    return out, {"needs_expansion": bool(issues), "issues": issues, "work_units": unit_count}
