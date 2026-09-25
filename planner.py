from __future__ import annotations

GENERIC_TITLES = {
    "implement", "implementation", "code", "write code", "triển khai", "viết code",
    "test", "kiểm thử", "document", "docs", "soạn tài liệu", "làm tài liệu"
}
CODE_CLASSES = {"code", "implementation", "coding", "refactor", "algorithm", "test", "testing"}
DISCOVERY_CLASSES = {"library_discovery", "dependency_discovery", "reuse_discovery"}

def hermes_plan_contract():
    """Three-layer planning contract with overlapped SCOUT procurement."""
    return {
        "owner": "cmd_control_plane",
        "pipeline": [
            "L1 mission: objective, scope, deliverables, constraints",
            "L2 execution_design: architecture, process, rules, candidate reusable libraries/tools",
            "SCOUT starts as soon as L2 candidates exist and runs concurrently while PLANNER continues independent planning",
            "planning_barrier: consume SCOUT capability_report before freezing library-dependent L3 details",
            "L3 work_plan: modules/functions, reuse mapping, algorithms for difficult functions, DAG, worker/model, acceptance criteria",
            "human review starts only after L3 is complete",
        ],
        "hierarchy": {"control_plane":"cmd","runtime":"hermes","default_model":"secretary","planner":"strong_reasoning","scout":"fast_research","coder":"execution","verifier":"independent_check"},
        "resolution": "task/work_unit/step",
        "hard_rules": [
            "The original user prompt is authoritative. Do not Grill/rewrite it before planning.",
            "PLANNER owns L1-L3 planning; SECRETARY only receives the request and maintains interaction/state.",
            "At L2 identify likely reusable components early. Dispatch SCOUT immediately; do not block PLANNER on work independent of the scout result.",
            "SCOUT returns a capability_report: selected/rejected libraries/tools, version/source, API/usage, integration notes, compatibility and evidence.",
            "Before freezing L3 library-dependent work, cross the planning_barrier and incorporate the capability_report.",
            "REIMPLEMENT_EXISTING_LIBRARY is forbidden when a suitable reusable component exists.",
            "Every L3 work_unit must state WHAT, WHO, WHEN/dependencies, HOW, and PASS/acceptance criteria.",
            "For difficult custom functions PLANNER supplies algorithm, inputs/outputs, edge cases and acceptance criteria so a cheaper CODER can execute without redesign.",
            "Use the smallest independently delegable work unit whose coordination overhead is worthwhile; group tiny tightly-coupled helpers.",
            "CODER must not redesign architecture/algorithm; unresolved contract problems escalate to PLANNER.",
            "VERIFIER may reject work but design changes escalate to PLANNER.",
            "Independent READY units run concurrently up to max_parallel with non-overlapping write scopes.",
            "Workers may not recursively orchestrate.",
        ],
        "shape": {
            "summary": "string",
            "layers": {
                "L1": {"objective":"string","scope":"string","deliverables":[],"constraints":[]},
                "L2": {"architecture":"string","process":[],"rules":[],"library_candidates":[],"scout_status":"DISPATCHED|DONE","capability_report":"object"},
                "L3": "tasks/work_units/steps"
            },
            "tasks": [{"id":"T1","title":"string","description":"WHAT","dependencies":[],
                "work_units":[{"id":"W1.1","title":"string","description":"WHAT","dependencies":[],"task_class":"...",
                    "role":"planner|scout|coder|verifier|integrator","symbol":"function/method/module","files":[],
                    "library_evidence":"reused component or reason custom code is necessary",
                    "provider":"CMD role-routed provider","model":"CMD role-routed model","reasoning":"WHO/why",
                    "execution":"HOW","verification":"PASS criteria","steps":[]}]}]
        },
    }

def _is_code(unit):
    cls=str(unit.get("task_class") or "").strip().lower()
    return cls in CODE_CLASSES or bool(unit.get("symbol"))

def normalize_plan(plan):
    plan = plan if isinstance(plan, dict) else {}
    out = {"summary": str(plan.get("summary") or ""), "layers": plan.get("layers") if isinstance(plan.get("layers"),dict) else {}, "tasks": []}
    issues = []
    layers=out["layers"]
    for key in ("L1","L2","L3"):
        if key not in layers: issues.append(f"planning layer {key} missing")
    l2=layers.get("L2") if isinstance(layers.get("L2"),dict) else {}
    if l2.get("library_candidates") and not l2.get("capability_report"):
        issues.append("planning_barrier: L2 library candidates exist but SCOUT capability_report is missing")
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
            if not str(unit.get("execution") or "").strip(): issues.append(f"{uid}: HOW/execution missing")
            if not str(unit.get("verification") or "").strip(): issues.append(f"{uid}: PASS/verification missing")
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
                "execution":str(unit.get("execution") or ""),"verification":str(unit.get("verification") or ""),"steps":steps,
            })
        out["tasks"].append({"id":tid,"title":str(task.get("title") or tid),"description":str(task.get("description") or ""),"dependencies":list(task.get("dependencies") or []),"task_class":str(task.get("task_class") or "general"),"risk":str(task.get("risk") or "medium"),"verification":str(task.get("verification") or ""),"work_units":normalized_units})
    if not out["tasks"]: issues.append("plan has no tasks")
    unit_count=sum(len(t["work_units"]) for t in out["tasks"])
    return out,{"needs_expansion":bool(issues),"issues":issues,"work_units":unit_count}
