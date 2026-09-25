from __future__ import annotations
import json, os
from pathlib import Path

DEFAULT_ROUTES={
 "cheap":{"model":"mimo-v2.6-flash","reason":"mechanical/low-risk work"},
 "balanced":{"model":"deepseek-v4-flash","reason":"general implementation and analysis"},
 "strong":{"model":"mimo-v2.6-pro","reason":"high-risk algorithm, architecture, or difficult reasoning"},
 "review":{"model":"deepseek-v4-flash","reason":"independent verification"},
}

def _routes():
    p=os.environ.get("CMD_MODEL_ROUTES","")
    if p and Path(p).exists():
        data=json.loads(Path(p).read_text(encoding="utf-8"))
        return {**DEFAULT_ROUTES,**data}
    return DEFAULT_ROUTES

def choose(unit: dict, mode: str="balanced") -> dict:
    risk=str(unit.get("risk","medium")).lower()
    cls=str(unit.get("task_class","general")).lower()
    text=(str(unit.get("title",""))+" "+str(unit.get("description",""))).lower()
    hard={"architecture","algorithm","state_machine","security","migration","debug_hard","reasoning"}
    easy={"format","rename","docs_simple","mechanical","search","boilerplate"}
    tier="balanced"
    if risk=="high" or cls in hard or any(x in text for x in ("race condition","state machine","architecture","root cause")): tier="strong"
    elif risk=="low" and (cls in easy or any(x in text for x in ("rename","format","boilerplate","simple docs"))): tier="cheap"
    if mode=="quality" and tier=="balanced": tier="strong"
    if mode=="cheap" and tier=="balanced": tier="cheap"
    route=dict(_routes()[tier]); route["tier"]=tier
    return route

def review_route() -> dict:
    r=dict(_routes()["review"]); r["tier"]="review"; return r
