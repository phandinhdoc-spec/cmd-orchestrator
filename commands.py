from __future__ import annotations
import json
from .config import VERSION, load_settings, save_settings
from .engine import create_plan, orchestrate
from .router import route
from .storage import STORE
from .rescue import rescue

def fmt_status(tasks=False):
    r=STORE.current()
    if not r: return f"CMD ORCHESTRATOR v{VERSION}\nNo saved run."
    ts=STORE.tasks(r["run_id"]); cp=STORE.latest_cp(r["run_id"])
    total=r.get("total_tasks",0) or 0; done=r.get("completed_tasks",0) or 0
    pct=int(done*100/total) if total else 0
    fill=round(pct/5); bar="█"*fill+"░"*(20-fill)
    cur=next((x for x in ts if x["task_id"]==r.get("current_task")),None) or {}
    out=[
      f"CMD ORCHESTRATOR v{VERSION}","",
      f"Project      : {r.get('project') or '-'}",
      f"Run          : {r['run_id']}",
      f"State        : {r['status']}",
      f"Mode         : {r.get('mode')}",
      f"Auto         : {r.get('auto_mode')}",
      f"Review       : {r.get('review_state')}",
      f"Progress     : {done}/{total}",
      f"{bar} {pct}%",
      f"Current      : {r.get('current_task') or '-'}",
      f"Provider     : {cur.get('provider') or '-'}",
      f"Model        : {cur.get('model') or '-'}",
      f"Checkpoint   : {(cp or {}).get('created_at',r.get('updated_at'))}",
      f"Reason       : {(cp or {}).get('event',r.get('last_checkpoint_reason'))}",
      "Resume-safe  : YES"
    ]
    if tasks:
        out+=["","Tasks:"]
        for t in ts: out.append(f"  {t['task_id']:<5} {t['status']:<11} {t['title']}  [{t.get('model') or '-'}]")
    return "\n".join(out)

def c_status(a): return STORE.current() and (json.dumps({"version":VERSION,"run":STORE.current(),"tasks":STORE.tasks(STORE.current()["run_id"])},ensure_ascii=False,indent=2) if "--json" in a else fmt_status("--tasks" in a)) or f"CMD ORCHESTRATOR v{VERSION}\nNo saved run."
def c_mode(a):
    x=(a or "").strip()
    st=load_settings()
    if not x: return f"mode={st['mode']}"
    if x not in ("cheap","balanced","quality","fast"): return "Usage: /cmd-mode <cheap|balanced|quality|fast>"
    st["mode"]=x; save_settings(st); return f"cmd-orchestrator mode -> {x}"
def c_auto(a):
    x=(a or "").strip()
    st=load_settings()
    if not x: return f"auto={st['auto']}"
    if x not in ("off","review","on"): return "Usage: /cmd-auto <off|review|on>"
    st["auto"]=x; save_settings(st); return f"cmd-orchestrator auto -> {x}"
def c_plan(a):
    req=(a or "").strip()
    if not req: return "Usage: /cmd-plan <công việc>"
    rid,p=create_plan(req)
    return f"Plan saved: {rid}\n\n"+json.dumps(p,ensure_ascii=False,indent=2)+"\n\nUse /cmd-review, then /cmd-run."
def c_review(a):
    r=STORE.current()
    if not r: return "No saved run."
    p=json.loads(r.get("plan_json") or "{}")
    return f"REVIEW {r['run_id']} [{r.get('review_state')}]\n\n"+json.dumps(p,ensure_ascii=False,indent=2)+"\n\nUse /cmd-run to approve+start, or /cmd-abort."
def make_run(ctx):
    def c_run(a):
        r=STORE.current()
        if not r: return "No saved run. Use /cmd-plan or /cmd-orchestrate first."
        STORE.set_run(r["run_id"],status="RUNNING",stage="execution",review_state="APPROVED")
        STORE.checkpoint(r["run_id"],"run_approved",{"source":"cmd-run"})
        instruction=(f"Continue cmd-orchestrator run {r['run_id']}. Execute only READY/PENDING tasks whose dependencies are DONE. "
                     "Use routed model/provider hints when available. Verify each task before marking DONE. "
                     "Checkpoint after important tool calls. Do not redo DONE tasks. At the end follow project Git/GitHub rules.")
        try:
            ctx.inject_message(instruction,role="user")
            return f"Run approved: {r['run_id']}\nExecution instruction injected into Hermes."
        except Exception as e:
            return f"Run approved: {r['run_id']}\nCould not inject automatically: {e}\nTell Hermes: {instruction}"
    return c_run
def c_route(a):
    s=(a or "").strip()
    if not s:return "Usage: /cmd-route <task>"
    return json.dumps(route(s),ensure_ascii=False,indent=2)
def c_checkpoint(a):
    r=STORE.current()
    if not r:return "No saved run."
    STORE.checkpoint(r["run_id"],"manual_checkpoint",{"note":a})
    return f"Checkpoint saved: {r['run_id']}"
def c_resume(a):
    r=STORE.resume((a or "").strip() or None)
    if not r:return "No resumable run."
    return f"Resumed: {r['run_id']}\n"+fmt_status(True)
def c_abort(a):
    r=STORE.current()
    if not r:return "No saved run."
    STORE.checkpoint(r["run_id"],"abort_requested",{"note":a})
    STORE.set_run(r["run_id"],status="ABORTED",stage="aborted")
    return f"Aborted safely: {r['run_id']}"
def c_history(a):
    rows=STORE.history()
    return "CMD HISTORY\n"+"\n".join(f"{x['run_id']}  {x['status']:<12} {x.get('completed_tasks',0)}/{x.get('total_tasks',0)}  {x.get('updated_at')}" for x in rows)
def c_learning(a):
    return json.dumps(STORE.learning_stats(),ensure_ascii=False,indent=2)
def c_models(a):
    return json.dumps(load_settings().get("models",{}),ensure_ascii=False,indent=2)
def c_rescue(a):
    return json.dumps(rescue(reason=(a or "manual /cmd-rescue")),ensure_ascii=False,indent=2)
def c_help(a):
    return """cmd-orchestrator v1.0 commands
/cmd-status [--tasks|--json]
/cmd-mode [cheap|balanced|quality|fast]
/cmd-auto [off|review|on]
/cmd-plan <work>
/cmd-review
/cmd-run
/cmd-route <task>
/cmd-models
/cmd-learning
/cmd-checkpoint
/cmd-resume [run_id]
/cmd-history
/cmd-rescue [reason]
/cmd-abort
/cmd-help
"""
