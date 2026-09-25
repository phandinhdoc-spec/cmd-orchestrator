from __future__ import annotations

GENERIC_TITLES = {
    "implement", "implementation", "code", "write code", "triển khai", "viết code",
    "test", "kiểm thử", "document", "docs", "soạn tài liệu", "làm tài liệu"
}
CODE_CLASSES = {"code", "implementation", "coding", "refactor", "algorithm", "test", "testing"}
DISCOVERY_CLASSES = {"library_discovery", "dependency_discovery", "reuse_discovery"}

def hermes_plan_contract():
    """Hard planning contract. CMD owns orchestration policy; Hermes is the execution runtime."""
    return {
        "owner": "cmd_control_plane",
        "hierarchy": {"control_plane":"cmd","runtime":"hermes","manager":"deepseek-v4-flash-fast","manager_fallback":"muse-spark-1.3-contributor","secretary":"muse-spark-1.3-contributor","planner":"agy/gemini-3.8-flash","incident_analyst":"sol|mimo-v4-pro confirmed-defect-only","patcher":"terra-class confirmed-defect-only","coder":"execution","verifier":"independent_check"},
        "resolution": "task/work_unit/step",
        "hard_rules": [
            "LIBRARY-FIRST: before custom implementation, search project dependencies, standard library/framework APIs, official packages, then suitable maintained third-party libraries.",
            "REIMPLEMENT_EXISTING_LIBRARY is forbidden. SCOUT searches for ready-made components/packages/tools first; searching how to recreate their internals is not acceptable discovery.",
            "PLANNER is HARD-LOCKED to Gemini 3.8 Flash through AGY for normal planning. Sol/MiMo V4 Pro are forbidden on the normal path.",
            "SECRETARY/SCOUT is HARD-LOCKED to Muse Spark 1.3 Contributor. MANAGER intelligence is DeepSeek V4 Flash Fast with Muse Spark 1.3 Contributor fallback.",
            "CODER receives a complete algorithm/contract from PLANNER and should use the cheapest capable coding model; CODER must not redesign architecture or algorithm.",
            "VERIFIER may reject normal work back to the planner. Sol/MiMo V4 Pro may enter only after user defect feedback AND Hermes confirms/reproduces the defect; they diagnose plan/algorithm root cause but do not patch. Hermes then selects the cheapest available Terra-class patcher and gives it a bounded patch packet containing original input/output/algorithm plus defect evidence.",
            "For code, one independently changeable function/method is one atomic work_unit by default.",
            "Tiny getters/setters/generated wrappers may be grouped only when agent startup/coordination would cost more than the work.",
            "Every custom implementation unit must depend on a library_discovery unit or carry explicit library_evidence explaining why no suitable reusable implementation exists.",
            "Independent READY work_units should be dispatched to separate workers concurrently up to max_parallel; do not serialize independent small units.",
            "Workers may not recursively orchestrate. CMD owns the orchestration policy/state; Hermes is the single execution runtime that dispatches CMD-approved work.",
            "Freeze shared interfaces/signatures before parallel dependent implementation; finish with integration/regression verification.",
        ],
        "rules": [
            "CMD owns orchestration policy, DAG state, role authority and run-to-completion. Strong PLANNER owns architecture/algorithm design. Hermes executes the resulting work packets and integration actions.",
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
                    "risk": "low|medium|high", "role": "planner|scout|coder|verifier|integrator", "provider": "CMD role-routed provider",
                    "model": "CMD role-routed model", "reasoning": "route rationale",
                    "verification": "acceptance evidence",
                    "steps": [{"id": "S1.1.1", "title": "string", "description": "string"}],
                }],
            }],
        },
    }

def _is_code(unit):
    cls=str(unit.get("task_class") or "").strip().lower()
    return cls in CODE_CLASSES or bool(unit.get("symbol"))

def _dag_issues(unit_ids, dependencies):
    """Validate work-unit dependency graph so execution cannot stall forever."""
    issues=[]
    known=set(unit_ids)
    for uid,deps in dependencies.items():
        for dep in deps:
            if dep == uid:
                issues.append(f"{uid}: self-dependency is forbidden")
            elif dep not in known:
                issues.append(f"{uid}: unknown dependency {dep}")
    graph={uid:[d for d in dependencies.get(uid,[]) if d in known and d != uid] for uid in known}
    state={}
    stack=[]
    reported=set()
    def visit(uid):
        state[uid]=1; stack.append(uid)
        for dep in graph.get(uid,[]):
            if state.get(dep,0)==0:
                visit(dep)
            elif state.get(dep)==1:
                try: cycle=stack[stack.index(dep):]+[dep]
                except ValueError: cycle=[dep,uid,dep]
                key=tuple(cycle)
                if key not in reported:
                    reported.add(key)
                    issues.append("dependency cycle: "+" -> ".join(cycle))
        stack.pop(); state[uid]=2
    for uid in sorted(known):
        if state.get(uid,0)==0: visit(uid)
    return issues

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
                "dependencies":deps,"task_class":cls,"role":str(unit.get("role") or ("scout" if cls.lower() in DISCOVERY_CLASSES else "coder" if _is_code(unit) else "worker")),"symbol":symbol,"files":files,
                "library_evidence":evidence,"risk":str(unit.get("risk") or "medium"),
                "provider":str(unit.get("provider") or ""),"model":str(unit.get("model") or ""),
                "reasoning":str(unit.get("reasoning") or "CMD role route"),
                "verification":str(unit.get("verification") or ""),"steps":steps,
            })
        out["tasks"].append({"id":tid,"title":str(task.get("title") or tid),"description":str(task.get("description") or ""),"dependencies":list(task.get("dependencies") or []),"task_class":str(task.get("task_class") or "general"),"risk":str(task.get("risk") or "medium"),"verification":str(task.get("verification") or ""),"work_units":normalized_units})
    if not out["tasks"]: issues.append("plan has no tasks")
    flat=[u for t in out["tasks"] for u in t["work_units"]]
    ids=[u["id"] for u in flat]
    dupes=sorted({uid for uid in ids if ids.count(uid)>1})
    issues.extend(f"{uid}: duplicate work_unit id" for uid in dupes)
    dependencies={u["id"]:list(u.get("dependencies") or []) for u in flat}
    issues.extend(_dag_issues(ids,dependencies))
    unit_count=len(flat)
    return out,{"needs_expansion":bool(issues),"issues":issues,"work_units":unit_count}
