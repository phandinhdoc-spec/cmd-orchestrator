from __future__ import annotations
import json, shutil, subprocess
from .config import RESCUE_DIR
from .storage import STORE

LIMIT_MARKERS=("429","rate limit","quota","too many requests","resource exhausted","usage limit","request limit")

def looks_limited(text):
    s=(text or "").lower()
    return any(x in s for x in LIMIT_MARKERS)

def fm_available():
    return shutil.which("fm") is not None

def rescue(run_id=None, reason="manual rescue"):
    r=STORE.run(run_id) if run_id else STORE.current()
    if not r: return {"ok":False,"message":"No saved run."}
    rid=r["run_id"]
    STORE.checkpoint(rid,"emergency_rescue",{"reason":reason})
    STORE.set_run(rid,status="INTERRUPTED",stage="rescue",error=reason)
    RESCUE_DIR.mkdir(parents=True,exist_ok=True)
    out=RESCUE_DIR/f"{rid}.md"
    tasks=STORE.tasks(rid)
    compact={"run":{k:r.get(k) for k in ("run_id","project","repository","status","current_stage","current_task","last_error")},
             "tasks":[{k:t.get(k) for k in ("task_id","title","status","verification","files_touched","output_summary")} for t in tasks]}
    if not fm_available():
        out.write_text("# Rescue checkpoint saved\n\n`fm` is not available in PATH. SQLite checkpoint is safe.\n",encoding="utf-8")
        return {"ok":False,"run_id":rid,"note":str(out),"fm":False}
    prompt=("Bạn là chế độ cứu hộ cục bộ. Chỉ dựa vào JSON sau, viết resume note ngắn bằng tiếng Việt: "
            "ĐÃ XONG / ĐANG DỞ / VIỆC TIẾP THEO / CẦN KIỂM TRA. Không bịa và không yêu cầu làm lại task DONE.\n"+
            json.dumps(compact,ensure_ascii=False))
    last=""
    for argv,stdin in ((["fm",prompt],None),(["fm"],prompt)):
        try:
            cp=subprocess.run(argv,input=stdin,text=True,capture_output=True,timeout=25)
            if cp.returncode==0 and cp.stdout.strip():
                out.write_text("# Apple Intelligence rescue note\n\n"+cp.stdout.strip()+"\n",encoding="utf-8")
                STORE.checkpoint(rid,"fm_rescue_success",{"note":str(out)})
                return {"ok":True,"run_id":rid,"note":str(out),"fm":True}
            last=(cp.stderr or cp.stdout or f"exit={cp.returncode}")[-1500:]
        except Exception as e:
            last=repr(e)
    out.write_text("# FM rescue failed\n\nSQLite checkpoint is safe.\n\n"+last,encoding="utf-8")
    STORE.checkpoint(rid,"fm_rescue_failed",{"error":last})
    return {"ok":False,"run_id":rid,"note":str(out),"fm":True}
