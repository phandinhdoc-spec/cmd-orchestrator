from __future__ import annotations
import logging
from .config import load_settings
from .storage import STORE
from .tools import SCHEMAS, HANDLERS
from .commands import (
    c_status,c_mode,c_auto,make_plan,c_prompt,c_review,c_edit,make_run,c_route,c_model,c_models,
    c_learn,c_learning,c_clean,c_checkpoint,c_resume,c_history,c_rescue,c_abort,c_help
)
from .rescue import looks_limited, rescue

log=logging.getLogger(__name__)

ORCHESTRATED_GUIDANCE = """cmd-orchestrator v1.4.0 is the CONTROL/MANAGEMENT PLANE; Hermes is the EXECUTION RUNTIME.

For substantial work, keep the user's original prompt authoritative. Do NOT invoke Grill/grill-tab or add a prompt-review round trip.

Planning is a pipelined three-layer process:
L1 MISSION — strong PLANNER states objective, scope, deliverables and constraints.
L2 EXECUTION DESIGN — PLANNER defines architecture, process/rules and likely reusable libraries/tools. As soon as candidates exist, dispatch SCOUT (prefer fast Muse Spark 1.3 Contributor when available) to investigate/acquire them, read APIs and produce a capability_report. PLANNER continues all independent planning concurrently; do not wait idly.
PLANNING BARRIER — before freezing library-dependent L3 details, consume SCOUT capability_report.
L3 WORK PLAN — list modules/functions, reuse mapping, algorithms/contracts for difficult custom functions, DAG, role/model and acceptance criteria. Every work_unit must say WHAT, WHO, WHEN/dependencies, HOW and PASS criteria. The plan is reviewable only after L3 validates.

After human approval, execute RUN-TO-COMPLETION. Recompute READY frontier after every completion, run independent non-conflicting work concurrently up to max_parallel, and stop only at DONE, an explicit approval gate, or a genuine human-decision blocker. Workers cannot recursively orchestrate. CODER may not redesign planner contracts; escalate contract defects to PLANNER. REIMPLEMENT_EXISTING_LIBRARY remains a hard failure."""


def register(ctx):
    for name,schema in SCHEMAS.items():
        ctx.register_tool(name=name,toolset="cmd-orchestrator",schema=schema,handler=HANDLERS[name])

    cmds=[
      ("cmd-status",c_status,"Show CMD control state and detailed Hermes work plan.","[--json]"),
      
      ("cmd-plan",make_plan(ctx),"Start layered L1→L2/SCOUT→L3 planning from the original prompt.","<work>"),
      ("cmd-review",c_review,"Review Hermes task/work_unit/step plan and routes.",""),
      ("cmd-edit",c_edit,"Edit a pending task/work_unit.","<ID> field=value ..."),
      ("cmd-run",make_run(ctx),"Approve reviewed Hermes plan and execute.",""),
      ("cmd-model",c_model,"Show Hermes models or override a pending work_unit route.","[W#.# auto|W#.# provider model]"),
      ("cmd-models",c_models,"Alias: show all models visible to Hermes.",""),
      ("cmd-learn",c_learn,"Review/edit/teach learning for Hermes.","[add|edit|approve|activate|disable|reject|delete ...]"),
      ("cmd-learning",c_learning,"Alias of /cmd-learn.",""),
      ("cmd-route",c_route,"Explain v1.3.2 routing ownership.","[task]"),
      ("cmd-mode",c_mode,"Compatibility cost/quality hint; Hermes still owns routing.","[cheap|balanced|quality|fast]"),
      ("cmd-auto",c_auto,"Set CMD intervention mode.","[off|review|on]"),
      ("cmd-clean",c_clean,"Preview/selectively clean CMD-generated artifacts or deep-clean CMD state.","[select IDs...|project|all] [--deep] [--learning]"),
      ("cmd-checkpoint",c_checkpoint,"Force a durable checkpoint.","[note]"),
      ("cmd-resume",c_resume,"Resume latest interrupted run.","[run_id]"),
      ("cmd-history",c_history,"Show recent runs.",""),
      ("cmd-rescue",c_rescue,"Checkpoint and call local fm rescue.","[reason]"),
      ("cmd-abort",c_abort,"Abort current run safely.","[reason]"),
      ("cmd-help",c_help,"Show v1.3.2 control-plane commands.","")]
    for n,h,d,ah in cmds:
        ctx.register_command(n,handler=h,description=d,args_hint=ah)

    def pre_llm_call(**kw):
        st=load_settings(); r=STORE.current()
        if r: STORE.checkpoint(r["run_id"],"pre_llm_call",{"session_id":kw.get("session_id","")})
        if st.get("auto","review")=="off": return None
        msg=(kw.get("user_message") or "").strip()
        if not msg or msg.startswith("/cmd-"): return None

        if r and r.get("status") not in ("DONE","FAILED","ABORTED"):
            stage=r.get("current_stage") or ""
            if stage.startswith("planning_"):
                return {"content":"CMD layered planning is active. Strong PLANNER: complete L1 mission, then L2 execution design. The moment L2 identifies candidate reusable libraries/tools, dispatch fast SCOUT concurrently and continue independent planning. Before finalizing L3, consume SCOUT capability_report at the planning barrier. L3 must specify WHAT/WHO/WHEN/HOW/PASS plus algorithms/contracts for difficult custom functions, then call cmd_capture_plan. Never invoke Grill."}
            if stage=="review":
                return {"content":"CMD stage=review. Apply requested edits with cmd_plan_patch. On approval call cmd_approve_run and immediately execute its returned run-to-completion instruction."}
            if stage in ("execution","resume"):
                return {"content":"CMD stage=execution. RUN-TO-COMPLETION: execute cmd_ready_batch frontier concurrently up to max_parallel. After each completion immediately recompute the frontier. Do not wait for another user prompt. Stop only at DONE, explicit approval gate, or genuine human blocker."}
            if stage in ("learning","learning_review"):
                return {"content":"CMD stage=learning. Capture concise evidence-based lessons with cmd_learning_capture."}
        return {"content":ORCHESTRATED_GUIDANCE}

    def post_tool_call(**kw):
        r=STORE.current()
        if not r:return None
        tool=kw.get("tool_name",""); result=str(kw.get("result",""))
        STORE.checkpoint(r["run_id"],"post_tool_call",{"tool":tool,"task_id":kw.get("task_id",""),"result_tail":result[-1000:]})
        if looks_limited(result) and load_settings().get("fm_rescue",True):
            try: rescue(r["run_id"],f"limit detected after tool {tool}")
            except Exception: log.exception("fm rescue failed")
        return None

    def on_session_start(**kw):
        STORE.recover_stale(); return None

    def on_session_end(**kw):
        r=STORE.current()
        if not r:return None
        if r.get("status") not in ("DONE","FAILED","ABORTED"):
            STORE.checkpoint(r["run_id"],"session_end",{"session_id":kw.get("session_id","")})
        else:
            STORE.ensure_learning_fallback(r["run_id"])
        return None

    for name,fn in (("pre_llm_call",pre_llm_call),("post_tool_call",post_tool_call),("on_session_start",on_session_start),("on_session_end",on_session_end)):
        ctx.register_hook(name,fn)

    def api_request_error(**kw):
        txt=str(kw); r=STORE.current()
        if r:
            STORE.checkpoint(r["run_id"],"api_request_error",{"error":txt[-2000:]})
            if looks_limited(txt) and load_settings().get("fm_rescue",True):
                rescue(r["run_id"],"provider quota/rate limit")
        return None
    try: ctx.register_hook("api_request_error",api_request_error)
    except Exception: pass
