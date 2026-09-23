from __future__ import annotations
import json,os,sqlite3,time
from pathlib import Path
from threading import RLock
from .config import RUN_DB

LOCK=RLock(); TERMINAL={"DONE","FAILED","ABORTED","SKIPPED"}; EDITABLE={"PENDING","READY","WAITING"}
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S%z")
def safe(v,n=8000):
    s="" if v is None else str(v); low=s.lower()
    if any(x in low for x in ("api_key","authorization:","bearer ","password=","secret=","token=")): return "[REDACTED]"
    return s[:n]
def con():
    c=sqlite3.connect(RUN_DB,timeout=5); c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL"); c.execute("PRAGMA foreign_keys=ON"); return c
def pid_alive(pid):
    try: os.kill(int(pid),0); return True
    except Exception:return False
def atomic_json(path:Path,data):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp")
    with open(tmp,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
