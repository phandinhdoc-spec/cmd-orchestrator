from __future__ import annotations
import json
from .engine import begin_prompt_review, select_prompt, capture_hermes_plan, patch_plan_item, approve_run, update_work_unit, complete_run, orchestrate
from .router import route
from .storage import STORE
from .config import hermes_model_catalog

SCHEMAS={
"cmd_prompt_capture":{"name":"cmd_prompt_capture","description":"Capture the full original and Grill Me prompts for mandatory human review before substantial work.","parameters":{"type":"object","properties":{"original_prompt":{"type":"string"},"grilled_prompt":{"type":"string"},"project":{"type":"string"},"repository":{"type":"string"}},"required":["original_prompt","grilled_prompt"]}},
"cmd_prompt_select":{"name":"cmd_prompt_select","description":"Record the human choice: original, grilled, or edited prompt.","parameters":{"type":"object","properties":{"selection":{"type":"string","enum":["original","grilled","edited"]},"edited_prompt":{"type":"string"},"run_id":{"type":"string"}},"required":["selection"]}},
"cmd_capture_plan":{"name":"cmd_capture_plan","description":"Store a detailed plan created by Hermes. Use task -> work_unit -> step. CMD validates resolution but does not invent planning decisions.","parameters":{"type":"object","properties":{"plan":{"type":"object"},"run_id":{"type":"string"}},"required":["plan"]}},
"cmd_plan_patch":{"name":"cmd_plan_patch","description":"Apply a human-requested edit to a not-yet-started task/work_unit.","parameters":{"type":"object","properties":{"item_id":{"type":"string"},"changes":{"type":"object"},"run_id":{"type":"string"}},"required":["item_id","changes"]}},
"cmd_approve_run":{"name":"cmd_approve_run","description":"Approve the reviewed Hermes plan and return execution instructions.","parameters":{"type":"object","properties":{"run_id":{"type":"string"}}}},
"cmd_unit_update":{"name":"cmd_unit_update","description":"Update execution state/evidence for one Hermes work_unit.","parameters":{"type":"object","properties":{"unit_id":{"type":"string"},"status":{"type":"string"},"verification":{"type":"string"},"output_summary":{"type":"string"},"files_touched":{"type":"array","items":{"type":"string"}},"attempts":{"type":"integer"},"error":{"type":"string"},"steps_done":{"type":"array","items":{"type":"string"}},"run_id":{"type":"string"}},"required":["unit_id"]}},
"cmd_complete_run":{"name":"cmd_complete_run","description":"Mark the Hermes run complete and enter learning/reflection stage.","parameters":{"type":"object","properties":{"success":{"type":"boolean"},"summary":{"type":"string"},"run_id":{"type":"string"}}}},
"cmd_learning_capture":{"name":"cmd_learning_capture","description":"Store Hermes reflection items as human-reviewable observations/lessons/rules.","parameters":{"type":"object","properties":{"items":{"type":"array","items":{"type":"object","properties":{"statement":{"type":"string"},"kind":{"type":"string"},"scope":{"type":"string"},"evidence":{"type":"string"},"confidence":{"type":"string"}},"required":["statement"]}},"run_id":{"type":"string"}},"required":["items"]}},
"cmd_learning_context":{"name":"cmd_learning_context","description":"Return user-approved/active lessons that Hermes should consider without surrendering orchestration authority.","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}},
"cmd_models_refresh":{"name":"cmd_models_refresh","description":"Return providers/models visible to Hermes. Hermes remains the default routing authority.","parameters":{"type":"object","properties":{}}},
# compatibility tools
"cmd_orchestrate":{"name":"cmd_orchestrate","description":"Compatibility entrypoint: begin CMD control workflow; Hermes still owns planning/routing.","parameters":{"type":"object","properties":{"request":{"type":"string"},"project":{"type":"string"},"repository":{"type":"string"}},"required":["request"]}},
"cmd_route":{"name":"cmd_route","description":"Compatibility routing preview. Returns that Hermes owns default routing plus learning context.","parameters":{"type":"object","properties":{"task":{"type":"string"},"task_class":{"type":"string"},"risk":{"type":"string"}},"required":["task"]}},
"cmd_learning_stats":{"name":"cmd_learning_stats","description":"Show historical verified model outcomes.","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}},
}

def _j(x): return json.dumps(x,ensure_ascii=False,indent=2)

def cmd_prompt_capture(p): return _j(begin_prompt_review(p["original_prompt"],p.get("grilled_prompt",""),p.get("project",""),p.get("repository","")))
def cmd_prompt_select(p): return _j(select_prompt(p["selection"],p.get("edited_prompt",""),p.get("run_id") or None))
def cmd_capture_plan(p): return _j(capture_hermes_plan(p["plan"],p.get("run_id") or None))
def cmd_plan_patch(p): return _j(patch_plan_item(p["item_id"],p.get("changes") or {},p.get("run_id") or None))
def cmd_approve_run(p): return _j(approve_run(p.get("run_id") or None))
def cmd_unit_update(p): return _j(update_work_unit(p["unit_id"],p.get("status"),p.get("verification",""),p.get("output_summary",""),p.get("files_touched"),p.get("attempts"),p.get("error",""),p.get("steps_done"),p.get("run_id") or None))
def cmd_complete_run(p): return _j(complete_run(p.get("success",True),p.get("summary",""),p.get("run_id") or None))
def cmd_models_refresh(p): return _j(hermes_model_catalog())
def cmd_orchestrate(p): return _j(orchestrate(p["request"],p.get("project",""),p.get("repository","")))
def cmd_route(p): return _j(route(p["task"],p.get("task_class","general"),p.get("risk","medium")))
def cmd_learning_stats(p): return _j(STORE.learning_stats(p.get("limit",30)))
def cmd_learning_context(p): return _j(STORE.relevant_learnings(p.get("limit",20)))
def cmd_learning_capture(p):
    r=STORE.run(p.get("run_id")) if p.get("run_id") else STORE.current()
    rid=r["run_id"] if r else ""
    ids=[]
    for item in p.get("items") or []:
        ids.append(STORE.add_learning(item.get("statement",""),kind=item.get("kind","lesson"),source="hermes",status="CANDIDATE",
                                      scope=item.get("scope","general"),evidence=item.get("evidence",""),confidence=item.get("confidence","medium"),run_id=rid))
    if r:
        STORE.checkpoint(rid,"hermes_learning_captured",{"learning_ids":ids})
        STORE.set_run(rid,stage="learning_review")
    return _j({"learning_ids":ids,"status":"CANDIDATE","note":"Human can approve/edit/reject with /cmd-learn."})

HANDLERS={name:globals()[name] for name in SCHEMAS}
