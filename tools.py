from __future__ import annotations
import json
from .engine import create_plan, orchestrate
from .router import route
from .storage import STORE
from .config import load_settings

SCHEMAS={
"cmd_plan":{"name":"cmd_plan","description":"Create and durably save a task plan without executing it.","parameters":{"type":"object","properties":{"request":{"type":"string"},"project":{"type":"string"},"repository":{"type":"string"}},"required":["request"]}},
"cmd_route":{"name":"cmd_route","description":"Choose a cost-aware model/provider tier for one task.","parameters":{"type":"object","properties":{"task":{"type":"string"},"task_class":{"type":"string"},"risk":{"type":"string"},"mode":{"type":"string"}},"required":["task"]}},
"cmd_orchestrate":{"name":"cmd_orchestrate","description":"Create a durable plan, route every task, and prepare the DAG for execution/review.","parameters":{"type":"object","properties":{"request":{"type":"string"},"project":{"type":"string"},"repository":{"type":"string"},"mode":{"type":"string"}},"required":["request"]}},
"cmd_models_refresh":{"name":"cmd_models_refresh","description":"Show the logical model map currently used by the orchestrator.","parameters":{"type":"object","properties":{}}},
"cmd_learning_stats":{"name":"cmd_learning_stats","description":"Show verified historical routing outcomes.","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}
}

def cmd_plan(p):
    rid,plan=create_plan(p["request"],p.get("project",""),p.get("repository",""))
    return json.dumps({"run_id":rid,"plan":plan},ensure_ascii=False,indent=2)
def cmd_route(p):
    return json.dumps(route(p["task"],p.get("task_class","general"),p.get("risk","medium"),p.get("mode")),ensure_ascii=False,indent=2)
def cmd_orchestrate(p):
    return json.dumps(orchestrate(p["request"],p.get("project",""),p.get("repository",""),p.get("mode")),ensure_ascii=False,indent=2)
def cmd_models_refresh(p):
    return json.dumps(load_settings().get("models",{}),ensure_ascii=False,indent=2)
def cmd_learning_stats(p):
    return json.dumps(STORE.learning_stats(p.get("limit",30)),ensure_ascii=False,indent=2)
HANDLERS={"cmd_plan":cmd_plan,"cmd_route":cmd_route,"cmd_orchestrate":cmd_orchestrate,"cmd_models_refresh":cmd_models_refresh,"cmd_learning_stats":cmd_learning_stats}
