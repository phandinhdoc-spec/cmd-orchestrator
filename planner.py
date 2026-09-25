from __future__ import annotations

GENERIC_TITLES = {
    "implement", "implementation", "code", "write code", "triển khai", "viết code",
    "test", "kiểm thử", "document", "docs", "soạn tài liệu", "làm tài liệu"
}
CODE_CLASSES = {"code", "implementation", "coding", "refactor", "algorithm", "test", "testing"}
DISCOVERY_CLASSES = {"library_discovery", "dependency_discovery", "reuse_discovery"}

def hermes_plan_contract():
    """Hard planning contract. Hermes owns orchestration; CMD enforces execution granularity/policy."""
    return {
        "owner": "hermes",
        "resolution": "task/work_unit/step",
        "hard_rules": [
            "LIBRARY-FIRST: before custom implementation, search project dependencies, standard library/framework APIs, official packages, then suitable maintained third-party libraries.",
            "REIMPLEMENT_EXISTING_LIBRARY is forbidden. If an existing library satisfies the requirement, create integration/configuration work instead of recreating it.",
            "For code, one independently changeable function/method is one atomic work_unit by default.",
            "Tiny getters/setters/generated wrappers may be grouped only when agent startup/coordination would cost more than the work.",
            "Every custom implementation unit must depend on a library_discovery unit or carry explicit library_evidence explaining why no suitable reusable implementation exists.",
            "Independent READY work_units should be dispatched to separate workers concurrently up to max_parallel; do not serialize independent small units.",
            "Workers may not recursively orchestrate. Hermes is the single parent orchestrator.",
            "Freeze shared interfaces/signatures before parallel dependent implementation; finish with integration/regression verification.",
        ],
        "rules": [
            "Hermes owns planning, dependency analysis, worker assignment, model selection, and final integration.",
            "Make the plan detailed enough to expose mixed difficulty and parallelism.",
            "A work_unit is the smallest independently routable/executable unit.",
            "Steps are an internal checklist, not routing boundaries.",
            "Put provider/model/reasoning on every work_unit.",
            "Use dependencies to form a DAG; avoid overlapping write scopes among concurrent workers.",
        ],
        "shape": {
            "summary": "string",
            "tasks": [{
                "id": "T1", "title": "string", "description": "string", "dependencies": [],
                "work_units": [{
                    "id": "W1.1", "title": "string", "description": "string",
                    "dependencies": [], "task_class": "library_discovery|implementation|test|integration|...",
                    "symbol": "function/method/module being changed",
                    "files": ["write-scope paths"],
                    "library_evidence": "packages/APIs checked, selected reusable library, or evidence custom code is necessary",
                    "risk": "low|medium|high", "provider": "Hermes-selected provider",
                    "model": "Hermes-selected model", "reasoning": "route rationale",
                    "verification": "acceptance evidence",
                    "steps": [{"id": "S1.1.1", "title": "string", "description": "string"}],
                }],
            }],
        },
    }

def _is_code(unit):
    cls=str(unit.get("task_class") or "").strip().lower()
    return cls in CODE_CLASSES or bool(unit.get("symbol"))

def normalize_plan(plan):
    plan = plan if isinstance(plan, dict) else {}
    out = {"summary": str(plan.get("summary") or ""), "tasks": []}
    issues = []
    all_raw_units=[]
    for t in plan.get("tasks") or []:
        if isinstance(t,dict):
            all_raw_units.extend(u for u in (t.get("work_units") or []) if isinstance(u,dict))
    discovery_ids={str(u.get("id") or "") for u in all_raw_units if str(u.get("task_class") or "").lower() in DISCOVERY_CLASSES}

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
            steps=[]
            for si, raw_step in enumerate(unit.get("steps") or [], 1):
                step=raw_step if isinstance(raw_step,dict) else {"title":str(raw_step)}
                steps.append({"id":str(step.get("id") or f"S{ti}.{ui}.{si}"),"title":str(step.get("title") or step.get("description") or "step"),"description":str(step.get("description") or "")})
            title=str(unit.get("title") or unit.get("description") or uid)
            deps=list(unit.get("dependencies") or [])
            cls=str(unit.get("task_class") or "general")
            evidence=str(unit.get("library_evidence") or "").strip()
            symbol=str(unit.get("symbol") or "").strip()
            files=list(unit.get("files") or [])
            if title.strip().lower() in GENERIC_TITLES and len(steps)<2:
                issues.append(f"{uid}: generic/coarse work_unit; expand it")
            if _is_code(unit) and cls.lower() not in DISCOVERY_CLASSES:
                if not evidence and not any(d in discovery_ids for d in deps):
                    issues.append(f"{uid}: custom code lacks library-first evidence/dependency")
                if cls.lower() in {"implementation","code","coding","refactor","algorithm"} and not symbol:
                    issues.append(f"{uid}: code unit must identify one atomic function/method in symbol (or justify grouping in library_evidence)")
            normalized_units.append({
                "id":uid,"title":title,"description":str(unit.get("description") or ""),
                "dependencies":deps,"task_class":cls,"symbol":symbol,"files":files,
                "library_evidence":evidence,"risk":str(unit.get("risk") or "medium"),
                "provider":str(unit.get("provider") or ""),"model":str(unit.get("model") or ""),
                "reasoning":str(unit.get("reasoning") or "Hermes route"),
                "verification":str(unit.get("verification") or ""),"steps":steps,
            })
        out["tasks"].append({"id":tid,"title":str(task.get("title") or tid),"description":str(task.get("description") or ""),"dependencies":list(task.get("dependencies") or []),"task_class":str(task.get("task_class") or "general"),"risk":str(task.get("risk") or "medium"),"verification":str(task.get("verification") or ""),"work_units":normalized_units})
    if not out["tasks"]: issues.append("plan has no tasks")
    unit_count=sum(len(t["work_units"]) for t in out["tasks"])
    return out,{"needs_expansion":bool(issues),"issues":issues,"work_units":unit_count}
