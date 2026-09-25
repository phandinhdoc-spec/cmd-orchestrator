from __future__ import annotations
from .config import load_settings
from .planner import normalize_plan, hermes_plan_contract
from .storage import STORE


def begin_prompt_review(original_prompt, grilled_prompt="", project="", repository="", session_id=""):
    st=load_settings()
    rid=STORE.create_run(original_prompt,project,repository,st.get("mode","balanced"),st.get("auto","review"),session_id)
    STORE.set_prompt(rid,original_prompt,grilled_prompt)
    return {"run_id":rid,"stage":"prompt_review","prompt":STORE.prompt(rid)}


def select_prompt(selection, edited_prompt="", run_id=None):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r:
        raise ValueError("no active run")
    selected=STORE.select_prompt(r["run_id"],selection,edited_prompt)
    return {"run_id":r["run_id"],"selected_prompt":selected,"next":"CMD delegates architecture/algorithm planning to a strong PLANNER through the Hermes runtime","contract":hermes_plan_contract()}


def capture_hermes_plan(plan, run_id=None):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r:
        raise ValueError("no active run")
    normalized,quality=normalize_plan(plan)
    STORE.set_plan(r["run_id"],normalized)
    if quality["needs_expansion"]:
        STORE.set_run(r["run_id"],status="PLANNING",stage="plan_expansion",review_state="PENDING")
        STORE.checkpoint(r["run_id"],"plan_needs_expansion",quality)
    else:
        STORE.set_run(r["run_id"],status="PLANNED",stage="review",review_state="PENDING")
    return {"run_id":r["run_id"],"quality":quality,"plan":normalized,"tree":STORE.plan_tree(r["run_id"])}


def patch_plan_item(item_id, changes, run_id=None):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r:
        raise ValueError("no active run")
    rid=r["run_id"]
    unit=STORE.unit(rid,item_id)
    if unit:
        if unit.get("status") not in ("PENDING","READY","WAITING"):
            raise ValueError(f"{item_id} is {unit.get('status')} and is locked")
        STORE.update_unit(rid,item_id,**changes)
        return {"kind":"work_unit","item":STORE.unit(rid,item_id)}
    task=STORE.task(rid,item_id)
    if task:
        if task.get("status") not in ("PENDING","READY","WAITING"):
            raise ValueError(f"{item_id} is {task.get('status')} and is locked")
        STORE.update_task(rid,item_id,**changes)
        return {"kind":"task","item":STORE.task(rid,item_id)}
    raise ValueError(f"unknown task/work_unit: {item_id}")


def approve_run(run_id=None):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r:
        raise ValueError("no active run")
    if not STORE.work_units(r["run_id"]):
        raise ValueError("no detailed Hermes work_units captured; plan must be expanded before execution")
    if r.get("current_stage")=="plan_expansion" or r.get("status")=="PLANNING":
        raise ValueError("plan still requires expansion/validation; capture a valid acyclic plan before execution")
    if r.get("review_state")=="APPROVED" and r.get("status")=="RUNNING":
        raise ValueError("run is already approved/running; refusing duplicate approval/instruction injection")
    STORE.set_run(r["run_id"],status="RUNNING",stage="execution",review_state="APPROVED")
    STORE.checkpoint(r["run_id"],"run_approved",{"source":"human_or_cmd"})
    return {
        "run_id":r["run_id"],
        "instruction": execution_instruction(r["run_id"]),
        "tree":STORE.plan_tree(r["run_id"]),
    }


def execution_instruction(rid):
    return (
        f"Execute cmd-orchestrator run {rid}. CMD is the control/management plane and owns orchestration policy/state; Hermes is the execution director/runtime. After human approval, this run is RUN-TO-COMPLETION: do not wait for another user message between approved work units. Recompute the READY frontier immediately whenever a unit finishes and continue until DONE, a declared approval gate, or a blocking failure that requires human input. Re-read the saved work_unit immediately before "
        "starting it because the operator may edit any READY/PENDING unit or route. Execute dependencies first. Role hierarchy is mandatory: the session/default model is SECRETARY only; architecture, algorithm and DAG decisions belong to a strong PLANNER (prefer Sol or DeepSeek V4 Pro when available). SCOUT workers search for ready-made libraries/packages/tools and their usage/API, not tutorials for recreating internals (prefer Muse Spark 1.3 Contributor when available). Before custom code, enforce library-first reuse. CODER workers receive the planner algorithm/contract and use the cheapest capable model; they must escalate instead of redesigning it. VERIFIER may reject but escalates design changes to PLANNER. For code, treat each independently changeable function/method work_unit as atomic. Call cmd_ready_batch to obtain the dependency-ready, write-scope-safe frontier, then dispatch each returned READY unit to a separate worker concurrently up to settings.max_parallel. Workers must not recursively orchestrate; CMD owns orchestration policy and Hermes performs runtime dispatch. Treat steps as "
        "an internal checklist, not separate agent calls unless Hermes decides that is necessary. Use the provider/model stored on "
        "each work_unit; route_source=operator overrides Hermes' original route. Verify each unit before DONE and checkpoint material "
        "progress. Each worker receives only cmd_work_packet for its unit, not the full plan. When a unit passes verification, immediately call cmd_unit_update status=DONE with a concise output_summary/files_touched: this is the SECRETARY check-in handed to Hermes. DONE/SKIPPED units are immutable and must be excluded from later worker context. If a model limits or is replaced, route the same unfinished work packet to the replacement model with explicit input/output/verification; do not make it reread the full plan. At the end call cmd_complete_run, then perform a concise Hermes reflection and call "
        "cmd_learning_capture with actual lessons; do not invent a rule from one weak observation."
    )


def work_packet(unit_id, run_id=None):
    """Minimal handoff contract for a worker/model replacement; no full-plan reread required."""
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r: raise ValueError("no active run")
    unit=STORE.unit(r["run_id"],unit_id)
    if not unit: raise ValueError(f"unknown work_unit: {unit_id}")
    if unit.get("status") in ("DONE","SKIPPED"):
        return {"run_id":r["run_id"],"unit_id":unit_id,"status":unit.get("status"),"immutable":True,
                "instruction":"Already completed and checked in. Do not inspect, redo, or modify this work unless an explicit replan invalidates it."}
    return {
        "run_id":r["run_id"],"unit_id":unit_id,"task_id":unit.get("task_id"),
        "input_contract":unit.get("description") or unit.get("title") or "",
        "dependencies":unit.get("dependencies") or [],
        "provider":unit.get("provider") or "","model":unit.get("model") or "",
        "verification":unit.get("verification") or "",
        "attempts":int(unit.get("attempts") or 0),
        "instruction":"Execute only this work packet and its stated acceptance/verification contract. Do not reread or redesign the full plan. If the assigned model changes or hits a limit, the replacement model continues from this packet plus the latest checkpoint/output summary.",
    }

def update_work_unit(unit_id, status=None, verification="", output_summary="", files_touched=None, attempts=None, error="", steps_done=None, run_id=None):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r: raise ValueError("no active run")
    rid=r["run_id"]
    unit=STORE.unit(rid,unit_id)
    if not unit: raise ValueError(f"unknown work_unit: {unit_id}")
    changes={}
    if status: changes["status"]=status.upper()
    if verification: changes["verification"]=verification
    if output_summary: changes["output_summary"]=output_summary
    if files_touched is not None: changes["files_touched"]=files_touched
    if attempts is not None: changes["attempts"]=int(attempts)
    if error: changes["last_error"]=error
    if changes.get("status")=="RUNNING": changes["started_at"]=unit.get("started_at") or __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z")
    if changes.get("status") in ("DONE","FAILED","SKIPPED"): changes["completed_at"]=__import__("time").strftime("%Y-%m-%dT%H:%M:%S%z")
    old_status=(unit.get("status") or "").upper()
    new_status=(changes.get("status") or old_status).upper()
    if old_status in ("DONE","SKIPPED") and new_status != old_status:
        raise ValueError(f"{unit_id} is checked in as {old_status} and immutable; explicit replan is required before reopening it")
    if old_status in ("DONE","SKIPPED") and any(k in changes for k in ("provider","model","output_summary","files_touched","verification","last_error")):
        raise ValueError(f"{unit_id} is checked in and immutable")
    STORE.update_unit(rid,unit_id,**changes)
    for sid in steps_done or []: STORE.update_step(rid,sid,"DONE")
    if changes.get("status") in ("DONE","SKIPPED"):
        for step in STORE.steps(rid,unit_id):
            if step.get("status")!="DONE": STORE.update_step(rid,step["step_id"],"DONE")
        STORE.checkpoint(rid,"unit_checkin",{
            "unit_id":unit_id,"status":changes.get("status"),
            "verification":verification,"output_summary":output_summary,
            "files_touched":files_touched or [],"model":unit.get("model"),"provider":unit.get("provider"),
            "instruction":"Secretary check-in: Hermes must treat this unit as completed/immutable and exclude it from future worker context."
        },unit_id)
    return {"run_id":rid,"unit":STORE.unit(rid,unit_id),"steps":STORE.steps(rid,unit_id),"checked_in":changes.get("status") in ("DONE","SKIPPED")}

def complete_run(success=True, summary="", run_id=None):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r:
        raise ValueError("no active run")
    rid=r["run_id"]
    unfinished=[u["unit_id"] for u in STORE.work_units(rid) if u.get("status") not in ("DONE","SKIPPED")]
    if success and unfinished:
        raise ValueError("cannot mark success; unfinished work_units: "+", ".join(unfinished))
    state="DONE" if success else "FAILED"
    STORE.set_run(rid,status=state,stage="learning",review_state="APPROVED",error="" if success else summary)
    STORE.checkpoint(rid,"run_completed",{"success":bool(success),"summary":summary})
    return {"run_id":rid,"status":state,"next":"Hermes reflection -> cmd_learning_capture"}

# Backward-compatible names. They now prepare control state; they do NOT independently plan/route.
def create_plan(request,project="",repository="",session_id=""):
    result=begin_prompt_review(request,"",project,repository,session_id)
    return result["run_id"], {"owner":"hermes","status":"awaiting_grill_or_prompt_selection","contract":hermes_plan_contract()}

def orchestrate(request,project="",repository="",mode=None,session_id=""):
    result=begin_prompt_review(request,"",project,repository,session_id)
    return {**result,"owner":"hermes","contract":hermes_plan_contract(),"note":"CMD v1.3.3 owns the control/management plane; Hermes is the agent runtime, strong planner designs, scouts procure reusable components, coders execute contracts."}
