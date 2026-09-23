from __future__ import annotations
import json
from .config import VERSION, load_settings, save_settings, hermes_model_catalog
from .engine import create_plan
from .router import route
from .storage import STORE
from .rescue import rescue

def _task_table(ts):
    if not ts: return ["  (no tasks)"]
    out=["  ID    STATUS       PROVIDER        MODEL                         TASK",
         "  ----  -----------  --------------  ----------------------------  ------------------------------"]
    for t in ts:
        out.append(f"  {t['task_id']:<4}  {t['status']:<11}  {(t.get('provider') or '-')[:14]:<14}  {(t.get('model') or '-')[:28]:<28}  {t.get('title') or '-'}")
        if t.get("reasoning"): out.append(f"        why: {t['reasoning']}")
    return out

def fmt_status(tasks=True):
    r=STORE.current()
    if not r: return f"CMD ORCHESTRATOR v{VERSION}\nNo saved run."
    ts=STORE.tasks(r["run_id"]); cp=STORE.latest_cp(r["run_id"])
    total=r.get("total_tasks",0) or 0; done=r.get("completed_tasks",0) or 0
    pct=int(done*100/total) if total else 0; fill=round(pct/5); bar="█"*fill+"░"*(20-fill)
    cur=next((x for x in ts if x["task_id"]==r.get("current_task")),None) or {}
    out=[f"CMD ORCHESTRATOR v{VERSION}","",f"Project      : {r.get('project') or '-'}",f"Run          : {r['run_id']}",
         f"State        : {r['status']} / {r.get('current_stage') or '-'}",f"Mode / Auto  : {r.get('mode')} / {r.get('auto_mode')}",
         f"Review       : {r.get('review_state')}",f"Progress     : {done}/{total}  {bar} {pct}%",
         f"Current      : {r.get('current_task') or '-'}",f"Current route: {cur.get('provider') or '-'} / {cur.get('model') or '-'}",
         f"Checkpoint   : {(cp or {}).get('created_at',r.get('updated_at'))}",
         f"Reason       : {(cp or {}).get('event',r.get('last_checkpoint_reason'))}","Resume-safe  : YES"]
    if tasks:
        out+=["","TASK / MODEL PLAN:",*_task_table(ts),"",
              "Change a not-yet-started task: /cmd-model <TASK_ID> <provider> <model>",
              "Return a task to automatic routing: /cmd-model <TASK_ID> auto"]
    return "\n".join(out)

def c_status(a):
    r=STORE.current()
    if not r: return f"CMD ORCHESTRATOR v{VERSION}\nNo saved run."
    if "--json" in (a or ""): return json.dumps({"version":VERSION,"run":r,"tasks":STORE.tasks(r["run_id"])},ensure_ascii=False,indent=2)
    return fmt_status(True)

def c_mode(a):
    x=(a or "").strip(); st=load_settings()
    if not x: return f"mode={st['mode']}"
    if x not in ("cheap","balanced","quality","fast"): return "Usage: /cmd-mode <cheap|balanced|quality|fast>"
    st["mode"]=x; save_settings(st); return f"cmd-orchestrator mode -> {x}"

def c_auto(a):
    x=(a or "").strip(); st=load_settings()
    if not x: return f"auto={st['auto']}"
    if x not in ("off","review","on"): return "Usage: /cmd-auto <off|review|on>"
    st["auto"]=x; save_settings(st); return f"cmd-orchestrator auto -> {x}"

def c_plan(a):
    req=(a or "").strip()
    if not req: return "Usage: /cmd-plan <công việc>"
    rid,_=create_plan(req)
    return f"Plan saved: {rid}\n\n"+fmt_status(True)+"\n\nReview routes above; use /cmd-model to change any task, then /cmd-run."

def c_review(a):
    r=STORE.current()
    if not r: return "No saved run."
    return f"REVIEW {r['run_id']} [{r.get('review_state')}]\n\n"+"\n".join(_task_table(STORE.tasks(r["run_id"])))+"\n\nChange READY/PENDING task: /cmd-model <TASK_ID> <provider> <model>\nRestore auto: /cmd-model <TASK_ID> auto\nThen use /cmd-run."

def make_run(ctx):
    def c_run(a):
        r=STORE.current()
        if not r: return "No saved run. Use /cmd-plan or /cmd-orchestrate first."
        STORE.set_run(r["run_id"],status="RUNNING",stage="execution",review_state="APPROVED")
        STORE.checkpoint(r["run_id"],"run_approved",{"source":"cmd-run"})
        instruction=(f"Continue cmd-orchestrator run {r['run_id']}. Before EACH task, re-read the saved task row and use its current provider/model route; "
                     "the operator may change routes for tasks that have not started yet. Execute only READY/PENDING tasks whose dependencies are DONE. "
                     "Verify each task before marking DONE. Checkpoint after important tool calls. Do not redo DONE tasks. At the end follow project Git/GitHub rules.")
        try:
            ctx.inject_message(instruction,role="user")
            return f"Run approved: {r['run_id']}\nExecution instruction injected into Hermes.\n\n"+fmt_status(True)
        except Exception as e:
            return f"Run approved: {r['run_id']}\nCould not inject automatically: {e}\nTell Hermes: {instruction}"
    return c_run

def c_route(a):
    s=(a or "").strip()
    if not s:return "Usage: /cmd-route <task>"
    return json.dumps(route(s),ensure_ascii=False,indent=2)

def c_model(a):
    raw=(a or "").strip()
    if not raw: return json.dumps(hermes_model_catalog(),ensure_ascii=False,indent=2)
    parts=raw.split()
    if len(parts)<2: return "Usage: /cmd-model <TASK_ID> auto | /cmd-model <TASK_ID> <provider> <model>"
    r=STORE.current()
    if not r:return "No saved run."
    tid=parts[0]
    task=next((t for t in STORE.tasks(r["run_id"]) if t["task_id"].lower()==tid.lower()),None)
    if not task:return f"Unknown task: {tid}"
    if task["status"] not in ("PENDING","READY"):
        return f"Cannot change {task['task_id']}: status={task['status']}. Only PENDING/READY tasks can be changed."
    if parts[1].lower()=="auto":
        rr=route(task.get("description",""),task.get("task_class","general"),task.get("risk","medium"),r.get("mode"))
        provider,model,reason=rr["provider"],rr["model"],"operator reset to auto; "+rr["reason"]
    else:
        if len(parts)<3:return "Usage: /cmd-model <TASK_ID> <provider> <model>"
        provider=parts[1]; model=" ".join(parts[2:]); reason="operator override"
    STORE.update_task(r["run_id"],task["task_id"],provider=provider,model=model,reasoning=reason)
    STORE.checkpoint(r["run_id"],"model_override",{"task_id":task["task_id"],"provider":provider,"model":model},task["task_id"])
    return f"Route updated: {task['task_id']} -> {provider} / {model}\n\n"+fmt_status(True)

def c_models(a): return json.dumps(hermes_model_catalog(),ensure_ascii=False,indent=2)
def c_checkpoint(a):
    r=STORE.current()
    if not r:return "No saved run."
    STORE.checkpoint(r["run_id"],"manual_checkpoint",{"note":a}); return f"Checkpoint saved: {r['run_id']}"
def c_resume(a):
    r=STORE.resume((a or "").strip() or None)
    if not r:return "No resumable run."
    return f"Resumed: {r['run_id']}\n"+fmt_status(True)
def c_abort(a):
    r=STORE.current()
    if not r:return "No saved run."
    STORE.checkpoint(r["run_id"],"abort_requested",{"note":a}); STORE.set_run(r["run_id"],status="ABORTED",stage="aborted")
    return f"Aborted safely: {r['run_id']}"
def c_history(a):
    rows=STORE.history(); return "CMD HISTORY\n"+"\n".join(f"{x['run_id']}  {x['status']:<12} {x.get('completed_tasks',0)}/{x.get('total_tasks',0)}  {x.get('updated_at')}" for x in rows)
def c_learning(a): return json.dumps(STORE.learning_stats(),ensure_ascii=False,indent=2)
def c_rescue(a): return json.dumps(rescue(reason=(a or "manual /cmd-rescue")),ensure_ascii=False,indent=2)
def c_help(a):
    return """cmd-orchestrator v1.1 commands
/cmd-status [--json]                 detailed run + task/model table
/cmd-mode [cheap|balanced|quality|fast]
/cmd-auto [off|review|on]
/cmd-plan <work>                     plan AND route every task before execution
/cmd-review                          inspect task/model plan
/cmd-run                             approve current plan and execute
/cmd-route <task>                    preview automatic routing
/cmd-model                           models visible to Hermes
/cmd-model <T#> <provider> <model>   override a not-yet-started task
/cmd-model <T#> auto                 restore automatic routing
/cmd-models                          alias: full Hermes-visible model catalog
/cmd-learning
/cmd-checkpoint
/cmd-resume [run_id]
/cmd-history
/cmd-rescue [reason]
/cmd-abort
/cmd-help
"""
