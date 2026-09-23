from __future__ import annotations
import json
from .config import load_settings
from .planner import plan
from .router import route
from .storage import STORE

def create_plan(request,project="",repository="",session_id=""):
    st=load_settings()
    rid=STORE.create_run(request,project,repository,st.get("mode","balanced"),st.get("auto","review"),session_id)
    p=plan(request)
    STORE.set_plan(rid,p)
    return rid,p

def orchestrate(request,project="",repository="",mode=None,session_id=""):
    st=load_settings()
    if mode: st["mode"]=mode
    rid,p=create_plan(request,project,repository,session_id)
    for t in p["tasks"]:
        rr=route(t["description"],t.get("task_class","general"),t.get("risk","medium"),st.get("mode"))
        STORE.update_task(rid,t["id"],provider=rr["provider"],model=rr["model"],reasoning=rr["reason"],status="READY")
    STORE.set_run(rid,status="PLANNED",stage="review" if st.get("auto")=="review" else "ready",
                  review_state="PENDING" if st.get("auto")=="review" else "APPROVED")
    return {"run_id":rid,"plan":p,"tasks":STORE.tasks(rid),"auto":st.get("auto"),"mode":st.get("mode")}
