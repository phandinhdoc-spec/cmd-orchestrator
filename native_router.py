from __future__ import annotations
import json, os, re
from pathlib import Path
from commandcode_adapter import list_models

# Defaults use exact IDs verified from Command Code's live catalog.
DEFAULT_ROUTES={
 "cheap":{"model":"meta/muse-spark-1.3-contributor","reason":"very low-cost mechanical work"},
 "fast":{"model":"deepseek/deepseek-v4-flash-fast","reason":"low-latency focused coding"},
 "balanced":{"model":"deepseek/deepseek-v4-flash","reason":"general implementation and reasoning"},
 "long_context":{"model":"xiaomi/mimo-v2.6-flash","reason":"efficient 1M-context repository work"},
 "strong":{"model":"xiaomi/mimo-v2.6-pro","reason":"difficult architecture/debugging"},
 "review":{"model":"deepseek/deepseek-v4.1-flash","reason":"independent multimodal-capable verification"},
}

def _routes():
    p=os.environ.get("CMD_MODEL_ROUTES","")
    if p and Path(p).exists():
        data=json.loads(Path(p).read_text(encoding="utf-8"))
        return {**DEFAULT_ROUTES,**data}
    return DEFAULT_ROUTES

def available_model_ids() -> set[str]:
    """Read the current account's live Command Code model catalog."""
    try:
        raw=list_models()
    except Exception:
        return set()
    ids=set()
    for line in raw.splitlines():
        m=re.match(r"^([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.:-]+)\\s", line.strip())
        if m:
            ids.add(m.group(1))
    return ids

def _validated(route: dict) -> dict:
    route=dict(route)
    live=available_model_ids()
    if live and route["model"] not in live:
        # Safe fallback confirmed by Command Code as its default model.
        route["model"]="deepseek/deepseek-v4-flash"
        route["reason"] += "; configured model unavailable, used live default"
    return route

def choose(unit: dict, mode: str="balanced") -> dict:
    risk=str(unit.get("risk","medium")).lower()
    cls=str(unit.get("task_class","general")).lower()
    text=(str(unit.get("title",""))+" "+str(unit.get("description",""))).lower()
    hard={"architecture","algorithm","state_machine","security","migration","debug_hard","reasoning"}
    easy={"format","rename","docs_simple","mechanical","search","boilerplate"}
    longish={"repo_analysis","large_refactor","documentation_deep","research"}
    tier="balanced"
    if risk=="high" or cls in hard or any(x in text for x in ("race condition","state machine","architecture","root cause")):
        tier="strong"
    elif cls in longish or any(x in text for x in ("whole repository","large codebase","long context")):
        tier="long_context"
    elif risk=="low" and (cls in easy or any(x in text for x in ("rename","format","boilerplate","simple docs"))):
        tier="cheap"
    if mode=="quality" and tier=="balanced": tier="strong"
    elif mode=="cheap" and tier=="balanced": tier="cheap"
    elif mode=="fast" and tier=="balanced": tier="fast"
    route=_validated(_routes()[tier]); route["tier"]=tier
    return route

def review_route() -> dict:
    r=_validated(_routes()["review"]); r["tier"]="review"; return r
