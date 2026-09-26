from __future__ import annotations
import logging
from .config import load_settings
from .storage import STORE
from .tools import SCHEMAS, HANDLERS
from .commands import (
    c_status,c_mode,c_auto,make_plan,c_prompt,c_review,c_edit,make_run,c_route,c_model,c_models,
    c_learn,c_learning,c_clean,make_clean_git,c_checkpoint,c_resume,c_history,c_rescue,c_abort,c_help
)
from .rescue import looks_limited, rescue

log=logging.getLogger(__name__)

ORCHESTRATED_GUIDANCE = """cmd-orchestrator v1.5.2 is the CONTROL/MANAGEMENT PLANE. Hermes is the EXECUTION DIRECTOR / AGENT RUNTIME, not the policy owner. The session default model is only the SECRETARY. Normal planning is HARD-LOCKED to Gemini 3.8 Flash through AGY. SECRETARY is HARD-LOCKED to Muse Spark 1.3 Contributor. MANAGER intelligence is HARD-LOCKED to DeepSeek V4 Flash Fast with Muse Spark 1.3 Contributor fallback. Sol/MiMo V4 Pro are incident-only.

For each new user request, Hermes first decides DIRECT vs ORCHESTRATED using its own judgment:
- DIRECT: simple, low-risk, obvious tool action. Execute directly with the most reliable direct tool (shell/API; Computer Use only when GUI is actually needed). Skip Grill and plan review.
- ORCHESTRATED: substantial/multi-part/mixed-difficulty work. Follow this protocol:
  1) Invoke Grill Me / grill-tab if available. Never silently replace the user prompt.
  2) Call cmd_prompt_capture with the FULL original prompt and FULL grilled prompt. Show both in full and wait for the human to choose original/grilled/edit.
  3) After selection, CMD delegates architecture/algorithm/DAG design through Hermes to the strong PLANNER; do not let the default SECRETARY model design the system. FIRST dispatch SCOUT research/procurement work to find ready-made components, libraries, packages and tools plus their usage/API (prefer Muse Spark 1.3 Contributor when available). Do not research how to recreate components when suitable components exist. Then the PLANNER creates/refines the plan. FIRST perform library/dependency discovery. Reuse existing project dependencies, standard/framework APIs, official packages, or maintained libraries; REIMPLEMENT_EXISTING_LIBRARY is a hard failure. Then use task -> work_unit -> step. For code, one independently changeable function/method = one atomic work_unit by default. A step normally is not an agent call.
  4) CMD chooses provider/model policy by ROLE; Hermes executes the selected route, not merely task difficulty: PLANNER=AGY/Gemini 3.8 Flash; SECRETARY/SCOUT=Muse Spark 1.3 Contributor; MANAGER=DeepSeek V4 Flash Fast with Muse Contributor fallback; CODER=cheapest capable packet worker; VERIFIER=independent checking. Sol/MiMo V4 Pro are forbidden unless a user-reported defect is confirmed by Hermes; then they diagnose only, and the cheapest available Terra-class model receives the bounded patch packet. CODER must escalate rather than redesign architecture/algorithm.  Call cmd_capture_plan. If CMD reports plan_needs_expansion, expand the coarse units; CMD must not invent the missing plan.
  5) Show the DSL-like /cmd-review. Human may edit pending tasks/work_units or override routes. If the human says OK/approve, call cmd_approve_run (or they may use /cmd-run).
  6) During execution re-read each work_unit before starting it. Build the READY frontier from the dependency DAG and dispatch independent units to separate workers concurrently up to max_parallel. Do not serialize independent small units. Prevent overlapping write scopes. Workers never recursively orchestrate; CMD remains the control-plane authority; Hermes remains the execution runtime. PENDING/READY work can change; RUNNING/DONE is locked.
  7) After verification call cmd_complete_run for BOTH success and terminal failure. Immediately obey github_sync_instruction: snapshot the entire project to its recorded repository with GitHub MCP only (NO git CLI), including failed/intermediate run artifacts and a run journal/manifest; exclude secrets/caches. Only after GitHub snapshot confirmation, reflect on what was actually learned, then call cmd_learning_capture. User-approved/user-taught learning has higher authority than inferred learning.
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
      ("cmd-route",c_route,"Explain v1.5.2 routing ownership.","[task]"),
      ("cmd-mode",c_mode,"Compatibility cost/quality hint; Hermes still owns routing.","[cheap|balanced|quality|fast]"),
      ("cmd-auto",c_auto,"Set CMD intervention mode.","[off|review|on]"),
      ("cmd-clean",c_clean,"Preview/selectively clean CMD-generated artifacts or deep-clean CMD state.","[select IDs...|project|all] [--deep] [--learning]"),\n      ("clean-git",make_clean_git(ctx),"Use GitHub MCP to delete only manifest-marked run trash while preserving final code and final md/txt.",""),
      ("cmd-checkpoint",c_checkpoint,"Force a durable checkpoint.","[note]"),
      ("cmd-resume",c_resume,"Resume latest interrupted run.","[run_id]"),
      ("cmd-history",c_history,"Show recent runs.",""),
      ("cmd-rescue",c_rescue,"Checkpoint and call local fm rescue.","[reason]"),
      ("cmd-abort",c_abort,"Abort current run safely.","[reason]"),
      ("cmd-help",c_help,"Show v1.5.2 control-plane commands.","")]
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
                return {"content":"CMD stage=planning. CMD owns orchestration policy; Hermes is the runtime. The default/session model is SECRETARY only. Delegate architecture, algorithm and DAG design ONLY to AGY/Gemini 3.8 Flash. Use Muse Spark 1.3 Contributor as SECRETARY/SCOUT to find ready-made libraries/tools and usage/API before custom code. Enforce library-first discovery and never recreate a suitable library. For code, decompose to one function/method per atomic work_unit by default. Produce/expand task -> work_unit -> step, model the dependency DAG and independent parallel units, then call cmd_capture_plan; route each work_unit with Hermes' model choice."}
            if stage=="review":
                return {"content":"CMD stage=review. If the user requests edits, apply them with cmd_plan_patch. If they approve/OK, call cmd_approve_run and execute its returned instruction."}
            if stage in ("execution","resume"):
                return {"content":"CMD stage=execution. This approved run is RUN-TO-COMPLETION: never wait for another user message merely because a work unit finished. Fetch cmd_work_packet for each READY unit before starting it; workers and replacement models must not reread the full plan. Execute the READY DAG frontier with separate workers concurrently up to max_parallel; do not serialize independent small work. Enforce library-first reuse, write-scope isolation, and no recursive worker orchestration. Honor human edits/route overrides only for not-yet-started units. After every completed unit immediately record a concise SECRETARY check-in via cmd_unit_update status=DONE, then recompute cmd_ready_batch and continue dispatching until DONE, an explicit approval gate, or a blocking failure requiring human input."}
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
