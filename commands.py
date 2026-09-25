from __future__ import annotations
import json, shlex
from .config import VERSION, load_settings, save_settings, hermes_model_catalog
from .dsl import render_prompt_review, render_plan, render_learning
from .engine import begin_prompt_review, select_prompt, patch_plan_item, approve_run
from .planner import hermes_plan_contract
from .storage import STORE, EDITABLE
from .rescue import rescue
from .cleanup import preview as clean_preview, format_preview as clean_format, clean_selected, clean_project, clean_all


def fmt_status(include_plan=True):
    r=STORE.current()
    if not r:
        return f"CMD CONTROL PLANE v{VERSION}\nNo saved run.\nCMD owns orchestration policy; Hermes is the execution runtime."
    cp=STORE.latest_cp(r["run_id"])
    units=STORE.work_units(r["run_id"])
    total=len(units) or r.get("total_tasks",0) or 0
    done=sum(1 for u in units if u.get("status")=="DONE") if units else r.get("completed_tasks",0) or 0
    pct=int(done*100/total) if total else 0
    current=next((u for u in units if u["unit_id"]==r.get("current_task")),None) or {}
    out=[
        f"CMD CONTROL PLANE v{VERSION}",
        "owner = CMD control plane; runtime = Hermes",
        f"run = {r['run_id']}",
        f"state = {r.get('status')}",
        f"stage = {r.get('current_stage') or '-'}",
        f"review = {r.get('review_state') or '-'}",
        f"progress = {done}/{total} ({pct}%)",
        f"current = {r.get('current_task') or '-'}",
        f"route = {(current.get('provider') or '-')}/{(current.get('model') or '-')}",
        f"route_source = {current.get('route_source') or '-'}",
        f"checkpoint = {(cp or {}).get('event',r.get('last_checkpoint_reason')) or '-'}",
    ]
    if r.get("current_stage")=="prompt_review":
        out += ["",render_prompt_review(STORE.prompt(r["run_id"]))]
    elif include_plan:
        out += ["",render_plan(STORE.plan_tree(r["run_id"]),r)]
    return "\n".join(out)


def c_status(a):
    r=STORE.current()
    if not r: return fmt_status(True)
    if "--json" in (a or ""):
        return json.dumps({"version":VERSION,"run":r,"prompt":STORE.prompt(r["run_id"]),"plan":STORE.plan_tree(r["run_id"])},ensure_ascii=False,indent=2)
    return fmt_status(True)


def c_mode(a):
    x=(a or "").strip(); st=load_settings()
    if not x: return f"mode={st.get('mode')} (compatibility hint only; CMD role policy owns routing)"
    if x not in ("cheap","balanced","quality","fast"): return "Usage: /cmd-mode <cheap|balanced|quality|fast>"
    st["mode"]=x; save_settings(st)
    return f"mode hint -> {x}; CMD role policy still owns planning/routing"


def c_auto(a):
    x=(a or "").strip(); st=load_settings()
    if not x: return f"auto={st.get('auto')}"
    if x not in ("off","review","on"): return "Usage: /cmd-auto <off|review|on>"
    st["auto"]=x; save_settings(st); return f"cmd control mode -> {x}"


def make_plan(ctx):
    def c_plan(a):
        req=(a or "").strip()
        if not req: return "Usage: /cmd-plan <công việc>"
        instruction=(
            "Manual /cmd-plan requested. CMD owns orchestration policy and delegates architecture/algorithm planning to a strong PLANNER through Hermes. First run Grill Me/grill-tab for the user's request if available, "
            f"then call cmd_prompt_capture with original_prompt={req!r} and the FULL grilled prompt. Show both full prompts and wait for selection. "
            "After selection, create a detailed task -> work_unit -> step plan; choose provider/model per independently routable work_unit; "
            "call cmd_capture_plan. If CMD reports coarse units, expand them. Then show /cmd-review and wait for approval."
        )
        try:
            ctx.inject_message(instruction,role="user")
            return "Manual CMD planning requested. Hermes runtime will run Grill Me; CMD will capture both prompts, then delegate the selected prompt to the strong PLANNER."
        except Exception as e:
            return f"Could not inject Hermes instruction: {e}\nTell Hermes:\n{instruction}"
    return c_plan


def c_prompt(a):
    r=STORE.current()
    if not r: return "No active run."
    raw=(a or "").strip()
    if not raw:
        return render_prompt_review(STORE.prompt(r["run_id"])) + "\n\nUse: /cmd-prompt original | grilled | edit <full prompt>"
    if raw.lower()=="original":
        select_prompt("original",run_id=r["run_id"])
    elif raw.lower()=="grilled":
        select_prompt("grilled",run_id=r["run_id"])
    elif raw.lower().startswith("edit "):
        select_prompt("edited",raw[5:].strip(),r["run_id"])
    else:
        return "Usage: /cmd-prompt original | grilled | edit <full prompt>"
    return render_prompt_review(STORE.prompt(r["run_id"])) + "\n\nPrompt selected. Hermes should now create the detailed plan."


def c_review(a):
    r=STORE.current()
    if not r: return "No saved run."
    text=render_plan(STORE.plan_tree(r["run_id"]),r)
    return text + "\n\nEdit pending work: /cmd-edit <ID> field=value ...\nHuman-only worker route override: /cmd-model <WORK_UNIT> <provider> <model> (locked roles cannot be changed)\nRestore Hermes route: /cmd-model <WORK_UNIT> auto\nApprove: /cmd-run"


def _parse_edits(raw):
    tokens=shlex.split(raw)
    changes={}
    for tok in tokens:
        if "=" not in tok: continue
        k,v=tok.split("=",1)
        k=k.strip(); v=v.strip()
        if k=="dependencies": v=[x for x in v.split(",") if x]
        changes[k]=v
    return changes


def c_edit(a):
    raw=(a or "").strip()
    if not raw: return "Usage: /cmd-edit <TASK_OR_WORK_UNIT> field=value [field=value ...]"
    parts=raw.split(maxsplit=1)
    if len(parts)<2: return "Usage: /cmd-edit <ID> title='...' description='...' dependencies=W1.1,W1.2 risk=high verification='...'"
    item_id,rest=parts
    changes=_parse_edits(rest)
    allowed={"title","description","dependencies","task_class","risk","verification"}
    changes={k:v for k,v in changes.items() if k in allowed}
    if not changes: return "No editable fields found. Fields: title, description, dependencies, task_class, risk, verification"
    try:
        patch_plan_item(item_id,changes)
    except Exception as e:
        return f"Edit rejected: {e}"
    return c_review("")


def make_run(ctx):
    def c_run(a):
        try:
            result=approve_run()
        except Exception as e:
            return f"Cannot run: {e}"
        try:
            ctx.inject_message(result["instruction"],role="user")
            return f"Approved: {result['run_id']}\nHermes execution instruction injected.\n\n"+fmt_status(True)
        except Exception as e:
            return f"Approved: {result['run_id']}\nCould not inject automatically: {e}\nTell Hermes:\n{result['instruction']}"
    return c_run


def c_model(a):
    """Human-only worker-route override. Locked system roles can never be changed here."""
    raw=(a or "").strip()
    if not raw:
        catalog=hermes_model_catalog()
        catalog["override_policy"]={
            "human_only":True,
            "scope":"pending worker work_units only",
            "locked_roles":["planner","secretary","manager","incident_analyst"],
            "patcher_policy":"confirmed-defect-only; select a Terra-class model, not necessarily Terra",
            "note":"Agents/tools cannot use /cmd-model to bypass v1.5 locked role policy."
        }
        return json.dumps(catalog,ensure_ascii=False,indent=2)
    parts=raw.split()
    if len(parts)<2: return "Usage: /cmd-model <WORK_UNIT> auto | /cmd-model <WORK_UNIT> <provider> <model>"
    r=STORE.current()
    if not r: return "No saved run."
    uid=parts[0]
    unit=STORE.unit(r["run_id"],uid)
    if not unit: return f"Unknown work_unit: {uid}."
    if unit.get("status") not in EDITABLE:
        return f"Cannot change {uid}: status={unit.get('status')}. Only not-yet-started worker work_units are editable."
    role=str(unit.get("executor") or "").strip().lower()
    locked={"planner","secretary","manager","incident_analyst"}
    if role in locked:
        return f"Override rejected: {uid} is role={role}, which is hard-locked by CMD v1.5 policy."
    if parts[1].lower()=="auto":
        STORE.reset_unit_to_hermes(r["run_id"],uid)
    else:
        if len(parts)<3: return "Usage: /cmd-model <WORK_UNIT> <provider> <model>"
        provider=parts[1]; model=" ".join(parts[2:])
        forbidden={"gemini-3.8-flash","muse-spark-1.3-contributor","deepseek-v4-flash-fast","sol","mimo-v4-pro"}
        if model.strip().lower() in forbidden:
            return "Override rejected: this model is reserved by a hard-locked system role. /cmd-model may override ordinary worker routes only."
        STORE.update_unit(r["run_id"],uid,provider=provider,model=model,reasoning="explicit human worker override",route_source="operator")
        STORE.checkpoint(r["run_id"],"human_worker_route_override",{"unit_id":uid,"provider":provider,"model":model},uid)
    return c_review("")

def c_models(a): return c_model("")

def c_route(a):
    return "CMD v1.2 does not independently choose the default route. Hermes chooses provider/model per work_unit; use /cmd-model only to inspect/override."


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
    STORE.ensure_learning_fallback(r["run_id"])
    return f"Aborted safely: {r['run_id']}"


def c_history(a):
    rows=STORE.history(); return "CMD HISTORY\n"+"\n".join(f"{x['run_id']}  {x['status']:<14} {x.get('completed_tasks',0)}/{x.get('total_tasks',0)}  {x.get('updated_at')}" for x in rows)


def c_learn(a):
    raw=(a or "").strip()
    if not raw:
        return render_learning(STORE.learnings(50)) + "\n\n/cmd-learn add <text> | edit <L#> <text> | approve <L#> | activate <L#> | disable <L#> | reject <L#> | delete <L#>"
    parts=raw.split(maxsplit=2)
    cmd=parts[0].lower()
    if cmd=="add":
        text=raw[len(parts[0]):].strip()
        if not text: return "Usage: /cmd-learn add <lesson/rule>"
        lid=STORE.add_learning(text,kind="rule",source="user",status="ACTIVE",scope="general",confidence="high",priority=100)
        return f"User-taught rule saved as {lid}.\n\n"+render_learning([STORE.learning(lid)])
    if len(parts)<2: return "Usage: /cmd-learn <edit|approve|activate|disable|reject|delete> <L#> [text]"
    lid=parts[1]
    if not STORE.learning(lid): return f"Unknown learning: {lid}"
    if cmd=="edit":
        if len(parts)<3 or not parts[2].strip(): return f"Usage: /cmd-learn edit {lid} <new statement>"
        STORE.update_learning(lid,statement=parts[2].strip(),source="user",priority=100)
    elif cmd=="approve": STORE.update_learning(lid,status="APPROVED",priority=max(80,int(STORE.learning(lid).get("priority") or 0)))
    elif cmd=="activate": STORE.update_learning(lid,status="ACTIVE")
    elif cmd=="disable": STORE.update_learning(lid,status="DISABLED")
    elif cmd=="reject": STORE.update_learning(lid,status="REJECTED")
    elif cmd=="delete":
        STORE.delete_learning(lid); return f"Deleted {lid}."
    else: return "Unknown action. Use edit/approve/activate/disable/reject/delete."
    return render_learning([STORE.learning(lid)])


def c_learning(a):
    return c_learn(a)


def c_clean(a):
    raw=(a or "").strip()
    if not raw:
        return clean_format(clean_preview("select",False)) + """
    
Choose one:
  /cmd-clean select P1 P2 ...     delete only selected CMD files
  /cmd-clean project              delete CMD files of the current project
  /cmd-clean project --deep       project files + matching CMD run snapshots
  /cmd-clean all                  delete all historical CMD artifact files
  /cmd-clean all --deep           reset all CMD runtime state too
  /cmd-clean all --deep --learning  ALSO delete learned memory (destructive)
"""
    parts=raw.split(); mode=parts[0].lower()
    deep="--deep" in parts; learning="--learning" in parts
    if mode in ("preview","list"):
        scope=parts[1].lower() if len(parts)>1 and not parts[1].startswith("--") else "select"
        return clean_format(clean_preview(scope,deep))
    if mode=="select":
        ids=[x for x in parts[1:] if not x.startswith("--")]
        if not ids: return clean_format(clean_preview("select",deep))+"\n\nSelect IDs, e.g. /cmd-clean select P1"
        return json.dumps(clean_selected(ids),ensure_ascii=False,indent=2)
    if mode=="project":
        return json.dumps(clean_project(deep),ensure_ascii=False,indent=2)
    if mode=="all":
        if learning and not deep:
            return "--learning is only accepted with: /cmd-clean all --deep --learning"
        return json.dumps(clean_all(deep,learning),ensure_ascii=False,indent=2)
    return "Usage: /cmd-clean [select <IDs...>|project|all] [--deep] [--learning]"


def c_rescue(a): return json.dumps(rescue(reason=(a or "manual /cmd-rescue")),ensure_ascii=False,indent=2)


def c_help(a):
    return f"""cmd-orchestrator v{VERSION} — Hermes control plane

DEFAULT FLOW
user prompt -> Hermes decides DIRECT vs ORCHESTRATED
ORCHESTRATED -> Grill Me -> full prompt review -> Hermes detailed plan -> task review -> run -> learning review

COMMANDS
/cmd-status [--json]                    full control state in DSL-like form
/cmd-prompt                              show FULL original + grilled prompts
/cmd-prompt original|grilled             choose prompt
/cmd-prompt edit <full prompt>            choose edited prompt
/cmd-plan <work>                          manually request Hermes planning (normally automatic)
/cmd-review                               task -> work_unit -> step plan + Hermes routes
/cmd-edit <ID> field=value ...            edit pending task/work_unit metadata
/cmd-run                                  approve reviewed plan
/cmd-model                                Hermes-visible model catalog
/cmd-model <W#.#> <provider> <model>      HUMAN-ONLY ordinary-worker override; locked role models forbidden
/cmd-model <W#.#> auto                    restore Hermes' original route
/cmd-models                               alias of /cmd-model
/cmd-learn                                show what Hermes/CMD/user taught the system
/cmd-learn add <text>                     teach Hermes a high-priority active rule
/cmd-learn edit <L#> <text>               correct a lesson
/cmd-learn approve|activate|disable|reject|delete <L#>
/cmd-checkpoint [note]
/cmd-resume [run_id]
/cmd-history
/cmd-clean                                preview CMD-generated files
/cmd-clean select <IDs...>                delete selected files
/cmd-clean project [--deep]               clean current project CMD artifacts
/cmd-clean all [--deep] [--learning]      clean all CMD artifacts/state
/cmd-rescue [reason]
/cmd-abort [reason]
/cmd-auto [off|review|on]
/cmd-mode [cheap|balanced|quality|fast]    compatibility hint only; Hermes owns routing
/cmd-help

PLAN CONTRACT
{json.dumps(hermes_plan_contract(),ensure_ascii=False,indent=2)}
"""
