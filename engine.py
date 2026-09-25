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
    return {"run_id":r["run_id"],"selected_prompt":selected,"next":"Hermes plans using the selected prompt","contract":hermes_plan_contract()}


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
    STORE.set_run(r["run_id"],status="RUNNING",stage="execution",review_state="APPROVED")
    STORE.checkpoint(r["run_id"],"run_approved",{"source":"human_or_cmd"})
    return {
        "run_id":r["run_id"],
        "instruction": execution_instruction(r["run_id"]),
        "tree":STORE.plan_tree(r["run_id"]),
    }


def execution_instruction(rid):
    return (
        f"Execute cmd-orchestrator run {rid}. Hermes remains the orchestrator. Re-read the saved work_unit immediately before "
        "starting it because the operator may edit any READY/PENDING unit or route. Execute dependencies first. Before custom code, enforce library-first reuse: inspect existing project dependencies, standard/framework APIs, official packages, and maintained libraries; never reimplement a suitable library. For code, treat each independently changeable function/method work_unit as atomic. Call cmd_ready_batch to obtain the dependency-ready, write-scope-safe frontier, then dispatch each returned READY unit to a separate worker concurrently up to settings.max_parallel. Workers must not recursively orchestrate; Hermes remains the sole parent orchestrator. Treat steps as "
        "an internal checklist, not separate agent calls unless Hermes decides that is necessary. Use the provider/model stored on "
        "each work_unit; route_source=operator overrides Hermes' original route. Verify each unit before DONE and checkpoint material "
        "progress. Do not redo DONE units. At the end call cmd_complete_run, then perform a concise Hermes reflection and call "
        "cmd_learning_capture with actual lessons; do not invent a rule from one weak observation."
    )


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
    STORE.update_unit(rid,unit_id,**changes)
    for sid in steps_done or []: STORE.update_step(rid,sid,"DONE")
    if changes.get("status") in ("DONE","SKIPPED"):
        for step in STORE.steps(rid,unit_id):
            if step.get("status")!="DONE": STORE.update_step(rid,step["step_id"],"DONE")
    return {"run_id":rid,"unit":STORE.unit(rid,unit_id),"steps":STORE.steps(rid,unit_id)}

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
    return {**result,"owner":"hermes","contract":hermes_plan_contract(),"note":"CMD v1.2 is a control plane; Hermes must produce the plan."}
