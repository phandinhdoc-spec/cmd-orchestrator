from __future__ import annotations
import concurrent.futures, json, os, re, time, uuid
from pathlib import Path
from .commandcode_adapter import invoke
from .native_router import choose, review_route

STATE=Path.home()/".commandcode"/"cmd-orchestrator"
RUNS=STATE/"runs"

def _ensure(): RUNS.mkdir(parents=True,exist_ok=True)
def _extract_json(s:str):
    s=s.strip()
    try:return json.loads(s)
    except Exception: pass
    m=re.search(r"\{.*\}",s,re.S)
    if not m: raise ValueError("planner did not return JSON")
    return json.loads(m.group(0))

def plan(request:str, project:str="", mode:str="balanced"):
    _ensure(); rid=time.strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6]
    planner=os.environ.get("CMD_PLANNER_MODEL","mimo-v2.6-pro")
    prompt=f"""You are the planning stage of cmd-orchestrator. Decompose the request into the smallest useful independently executable work_units. Expose mixed difficulty: design, hard/easy functions, tests, integration and docs must be separate when appropriate. Steps are checklists, not separate workers. Return JSON only:
{{"summary":"...","work_units":[{{"id":"W1","title":"...","description":"...","task_class":"...","risk":"low|medium|high","dependencies":[],"steps":["..."],"verification":"..."}}]}}
REQUEST:
{request}
"""
    raw=invoke(prompt,planner,project)
    data=_extract_json(raw)
    units=data.get("work_units") or []
    for i,u in enumerate(units,1):
        u.setdefault("id",f"W{i}"); u.setdefault("dependencies",[]); u.setdefault("steps",[])
        u["route"]=choose(u,mode); u["status"]="PENDING"; u["attempts"]=0
    state={"run_id":rid,"request":request,"project":project,"mode":mode,"status":"PLANNED","summary":data.get("summary",""),"work_units":units}
    (RUNS/f"{rid}.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    (STATE/"current").write_text(rid,encoding="utf-8")
    return state

def load(rid:str=""):
    _ensure()
    if not rid: rid=(STATE/"current").read_text().strip()
    return json.loads((RUNS/f"{rid}.json").read_text(encoding="utf-8"))

def save(st):
    (RUNS/f"{st['run_id']}.json").write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding="utf-8")

def _worker(u,st):
    deps="\n".join(f"- {x}" for x in u.get("dependencies",[])) or "none"
    prompt=f"""You are CommandCode worker {u['id']} in cmd-orchestrator run {st['run_id']}.
Work ONLY on this work unit. Do not broaden scope. Inspect the repository before editing.
Title: {u['title']}
Description: {u.get('description','')}
Checklist: {json.dumps(u.get('steps',[]),ensure_ascii=False)}
Dependencies: {deps}
Verification required: {u.get('verification','')}
When finished, run the relevant verification and end with a concise WORKER_RESULT including files changed, tests, and unresolved risks.
"""
    return invoke(prompt,u["route"]["model"],st.get("project",""))

def run(rid:str="", max_parallel:int=3):
    st=load(rid); st["status"]="RUNNING"; save(st)
    while True:
        pending=[u for u in st["work_units"] if u["status"]=="PENDING"]
        if not pending: break
        done={u["id"] for u in st["work_units"] if u["status"]=="DONE"}
        ready=[u for u in pending if set(u.get("dependencies",[]))<=done]
        if not ready:
            st["status"]="BLOCKED"; save(st); raise RuntimeError("dependency deadlock or failed prerequisite")
        batch=ready[:max_parallel]
        for u in batch: u["status"]="RUNNING"; u["attempts"]+=1
        save(st)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as ex:
            fut={ex.submit(_worker,u,st):u for u in batch}
            for f,u in fut.items():
                try:
                    u["output"]=f.result(); u["status"]="DONE"
                except Exception as e:
                    u["error"]=str(e); u["status"]="FAILED"
        save(st)
        if any(u["status"]=="FAILED" for u in batch):
            st["status"]="FAILED"; save(st); return st
    st["status"]="DONE"; save(st); return st

def status(rid:str=""): return load(rid)
