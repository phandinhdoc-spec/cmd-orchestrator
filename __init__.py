from __future__ import annotations
import logging
from .config import load_settings
from .storage import STORE
from .tools import SCHEMAS, HANDLERS
from .commands import c_status,c_mode,c_auto,c_plan,c_review,make_run,c_route,c_model,c_models,c_learning,c_checkpoint,c_resume,c_history,c_rescue,c_abort,c_help
from .rescue import looks_limited, rescue
log=logging.getLogger(__name__)

def register(ctx):
    for name,schema in SCHEMAS.items(): ctx.register_tool(name=name,toolset="cmd-orchestrator",schema=schema,handler=HANDLERS[name])
    cmds=[
      ("cmd-status",c_status,"Show detailed run status and task/model plan.","[--json]"),
      ("cmd-mode",c_mode,"Set routing mode.","[cheap|balanced|quality|fast]"),
      ("cmd-auto",c_auto,"Set orchestration automation mode.","[off|review|on]"),
      ("cmd-plan",c_plan,"Create, route, save and show a plan.","<work>"),
      ("cmd-review",c_review,"Review task/model routes before execution.",""),
      ("cmd-run",make_run(ctx),"Approve current plan and start execution.",""),
      ("cmd-route",c_route,"Preview routing choice for a task.","<task>"),
      ("cmd-model",c_model,"Show Hermes models or override a pending task route.","[TASK_ID auto|TASK_ID provider model]"),
      ("cmd-models",c_models,"Show all models visible to Hermes.",""),
      ("cmd-learning",c_learning,"Show adaptive routing statistics.",""),
      ("cmd-checkpoint",c_checkpoint,"Force a durable checkpoint.","[note]"),
      ("cmd-resume",c_resume,"Resume latest interrupted run.","[run_id]"),
      ("cmd-history",c_history,"Show recent orchestration runs.",""),
      ("cmd-rescue",c_rescue,"Save emergency checkpoint and call local fm rescue.","[reason]"),
      ("cmd-abort",c_abort,"Abort current run after checkpoint.","[reason]"),
      ("cmd-help",c_help,"Show cmd-orchestrator commands.","")]
    for n,h,d,ah in cmds: ctx.register_command(n,handler=h,description=d,args_hint=ah)

    def pre_llm_call(**kw):
        st=load_settings(); r=STORE.current()
        if r: STORE.checkpoint(r["run_id"],"pre_llm_call",{"session_id":kw.get("session_id","")})
        auto=st.get("auto","review")
        if auto=="off": return None
        msg=(kw.get("user_message") or "").strip()
        if not msg or msg.startswith("/cmd-"): return None
        if auto=="review": return {"content":"cmd-orchestrator AUTO=review: for substantial work, call cmd_plan/cmd_orchestrate first. Show the task/model table and wait for /cmd-run; the operator may override routes with /cmd-model."}
        if auto=="on": return {"content":"cmd-orchestrator AUTO=on: call cmd_orchestrate for substantial work. Before each task re-read its saved route because the operator may override any not-yet-started task. Follow the DAG, checkpoint and verify."}
        return None

    def post_tool_call(**kw):
        r=STORE.current()
        if not r:return None
        tool=kw.get("tool_name",""); result=str(kw.get("result",""))
        STORE.checkpoint(r["run_id"],"post_tool_call",{"tool":tool,"task_id":kw.get("task_id",""),"result_tail":result[-1000:]})
        if looks_limited(result) and load_settings().get("fm_rescue",True):
            try: rescue(r["run_id"],f"limit detected after tool {tool}")
            except Exception: log.exception("fm rescue failed")
        return None

    def on_session_start(**kw): STORE.recover_stale(); return None
    def on_session_end(**kw):
        r=STORE.current()
        if r and r.get("status") not in ("DONE","FAILED","ABORTED"): STORE.checkpoint(r["run_id"],"session_end",{"session_id":kw.get("session_id","")})
        return None
    for name,fn in (("pre_llm_call",pre_llm_call),("post_tool_call",post_tool_call),("on_session_start",on_session_start),("on_session_end",on_session_end)): ctx.register_hook(name,fn)

    def api_request_error(**kw):
        txt=str(kw); r=STORE.current()
        if r:
            STORE.checkpoint(r["run_id"],"api_request_error",{"error":txt[-2000:]})
            if looks_limited(txt) and load_settings().get("fm_rescue",True): rescue(r["run_id"],"provider quota/rate limit")
        return None
    try: ctx.register_hook("api_request_error",api_request_error)
    except Exception: pass
