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

ORCHESTRATED_GUIDANCE = """cmd-orchestrator v1.3.1 is a CONTROL PLANE, not a replacement orchestrator.
Hermes remains the CEO/orchestrator. The session default model is only the SECRETARY. Substantial planning/architecture/algorithm work must be delegated to a strong PLANNER (prefer Sol or DeepSeek V4 Pro when available).

For each new user request, Hermes first decides DIRECT vs ORCHESTRATED using its own judgment:
- DIRECT: simple, low-risk, obvious tool action. Execute directly with the most reliable direct tool (shell/API; Computer Use only when GUI is actually needed). Skip Grill and plan review.
- ORCHESTRATED: substantial/multi-part/mixed-difficulty work. Follow this protocol:
  1) Invoke Grill Me / grill-tab if available. Never silently replace the user prompt.
  2) Call cmd_prompt_capture with the FULL original prompt and FULL grilled prompt. Show both in full and wait for the human to choose original/grilled/edit.
  3) After selection, Hermes delegates architecture/algorithm/DAG design to the strong PLANNER; do not let the default SECRETARY model design the system. FIRST dispatch SCOUT research/procurement work to find ready-made components, libraries, packages and tools plus their usage/API (prefer Muse Spark 1.3 Contributor when available). Do not research how to recreate components when suitable components exist. Then the PLANNER creates/refines the plan. FIRST perform library/dependency discovery. Reuse existing project dependencies, standard/framework APIs, official packages, or maintained libraries; REIMPLEMENT_EXISTING_LIBRARY is a hard failure. Then use task -> work_unit -> step. For code, one independently changeable function/method = one atomic work_unit by default. A step normally is not an agent call.
  4) Hermes chooses provider/model by ROLE, not merely task difficulty: PLANNER=strong reasoning; SCOUT=fast research/procurement; CODER=cheapest capable model executing a complete planner algorithm/contract; VERIFIER=independent checking. CODER must escalate rather than redesign architecture/algorithm.  Call cmd_capture_plan. If CMD reports plan_needs_expansion, expand the coarse units; CMD must not invent the missing plan.
  5) Show the DSL-like /cmd-review. Human may edit pending tasks/work_units or override routes. If the human says OK/approve, call cmd_approve_run (or they may use /cmd-run).
  6) During execution re-read each work_unit before starting it. Build the READY frontier from the dependency DAG and dispatch independent units to separate workers concurrently up to max_parallel. Do not serialize independent small units. Prevent overlapping write scopes. Workers never recursively orchestrate; Hermes remains the sole parent orchestrator. PENDING/READY work can change; RUNNING/DONE is locked.
  7) After verification call cmd_complete_run, reflect on what was actually learned, then call cmd_learning_capture. User-approved/user-taught learning has higher authority than inferred learning.
  8) Before substantial future work call cmd_learning_context and consider relevant ACTIVE/APPROVED lessons, without surrendering Hermes' orchestration authority.
"""

def register(ctx):
    for name,schema in SCHEMAS.items():
        ctx.register_tool(name=name,toolset="cmd-orchestrator",schema=schema,handler=HANDLERS[name])

    cmds=[
      ("cmd-status",c_status,"Show CMD control state and detailed Hermes work plan.","[--json]"),
      ("cmd-prompt",c_prompt,"Review/select the full original vs Grill Me prompt.","[original|grilled|edit <prompt>]"),
      ("cmd-plan",make_plan(ctx),"Manually ask Hermes for a detailed plan; normally automatic.","<work>"),
      ("cmd-review",c_review,"Review Hermes task/work_unit/step plan and routes.",""),
      ("cmd-edit",c_edit,"Edit a pending task/work_unit.","<ID> field=value ..."),
      ("cmd-run",make_run(ctx),"Approve reviewed Hermes plan and execute.",""),
      ("cmd-model",c_model,"Show Hermes models or override a pending work_unit route.","[W#.# auto|W#.# provider model]"),
      ("cmd-models",c_models,"Alias: show all models visible to Hermes.",""),
      ("cmd-learn",c_learn,"Review/edit/teach learning for Hermes.","[add|edit|approve|activate|disable|reject|delete ...]"),
      ("cmd-learning",c_learning,"Alias of /cmd-learn.",""),
      ("cmd-route",c_route,"Explain v1.3.1 routing ownership.","[task]"),
      ("cmd-mode",c_mode,"Compatibility cost/quality hint; Hermes still owns routing.","[cheap|balanced|quality|fast]"),
      ("cmd-auto",c_auto,"Set CMD intervention mode.","[off|review|on]"),
      ("cmd-clean",c_clean,"Preview/selectively clean CMD-generated artifacts or deep-clean CMD state.","[select IDs...|project|all] [--deep] [--learning]"),
      ("cmd-checkpoint",c_checkpoint,"Force a durable checkpoint.","[note]"),
      ("cmd-resume",c_resume,"Resume latest interrupted run.","[run_id]"),
      ("cmd-history",c_history,"Show recent runs.",""),
      ("cmd-rescue",c_rescue,"Checkpoint and call local fm rescue.","[reason]"),
      ("cmd-abort",c_abort,"Abort current run safely.","[reason]"),
      ("cmd-help",c_help,"Show v1.3.1 control-plane commands.","")]
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
            if stage=="prompt_review":
                return {"content":"CMD stage=prompt_review. Interpret the user's reply as choosing/editing the displayed FULL prompt; call cmd_prompt_select. Do not execute the substantive task yet."}
            if stage in ("hermes_plan","plan_expansion"):
                return {"content":"CMD stage=Hermes planning. Hermes orchestrates, but the default/session model is SECRETARY only. Delegate architecture, algorithm and DAG design to a strong PLANNER (prefer Sol or DeepSeek V4 Pro when available). Use fast SCOUT workers (prefer Muse Spark 1.3 Contributor when available) to find ready-made libraries/tools and usage/API before custom code. Enforce library-first discovery and never recreate a suitable library. For code, decompose to one function/method per atomic work_unit by default. Produce/expand task -> work_unit -> step, model the dependency DAG and independent parallel units, then call cmd_capture_plan; route each work_unit with Hermes' model choice."}
            if stage=="review":
                return {"content":"CMD stage=review. If the user requests edits, apply them with cmd_plan_patch. If they approve/OK, call cmd_approve_run and execute its returned instruction."}
            if stage in ("execution","resume"):
                return {"content":"CMD stage=execution. Re-read units before starting them. Execute the READY DAG frontier with separate workers concurrently up to max_parallel; do not serialize independent small work. Enforce library-first reuse, write-scope isolation, and no recursive worker orchestration. Honor human edits/route overrides only for not-yet-started units. Continue Hermes orchestration."}
            if stage in ("learning","learning_review"):
                return {"content":"CMD stage=learning. Hermes should record concise evidence-based reflection through cmd_learning_capture; the human may edit/approve it with /cmd-learn."}

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
