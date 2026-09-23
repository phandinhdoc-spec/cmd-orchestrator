from __future__ import annotations
import sqlite3,time
from .config import LEARN_DB, ensure_dirs

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S%z")
def safe(v,n=8000):
    s="" if v is None else str(v); low=s.lower()
    if any(x in low for x in ("api_key","authorization:","bearer ","password=","secret=","token=")): return "[REDACTED]"
    return s[:n]

class LearningStore:
    def __init__(self): ensure_dirs(); self.init()
    def con(self):
        c=sqlite3.connect(LEARN_DB,timeout=5); c.row_factory=sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=FULL"); return c
    def init(self):
        with self.con() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS outcomes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,task_class TEXT,provider TEXT,model TEXT,
              success INTEGER,verified INTEGER,attempts INTEGER,latency_ms INTEGER,cost_hint TEXT,error TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS learnings(
              id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,kind TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL,
              scope TEXT,statement TEXT NOT NULL,evidence TEXT,confidence TEXT,priority INTEGER DEFAULT 0,
              created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_learnings_status ON learnings(status,priority DESC,updated_at DESC);
            """)
    def stats(self,limit=30):
        with self.con() as c:
            return [dict(r) for r in c.execute("""SELECT task_class,provider,model,COUNT(*) n,SUM(success) success_n,
                SUM(verified) verified_n,ROUND(AVG(latency_ms),1) avg_latency_ms FROM outcomes
                GROUP BY task_class,provider,model ORDER BY n DESC LIMIT ?""",(int(limit),)).fetchall()]
    def add(self,statement,kind="observation",source="cmd",status="CANDIDATE",scope="general",evidence="",confidence="medium",priority=None,run_id=""):
        source=(source or "cmd").lower(); status=(status or "CANDIDATE").upper(); kind=(kind or "observation").lower()
        if priority is None: priority=100 if source=="user" else 70 if source=="hermes" else 20
        t=now()
        with self.con() as c:
            cur=c.execute("""INSERT INTO learnings(run_id,kind,source,status,scope,statement,evidence,confidence,priority,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(safe(run_id,128),safe(kind,32),safe(source,32),safe(status,24),safe(scope,120),safe(statement),safe(evidence),safe(confidence,24),int(priority),t,t))
            return f"L{cur.lastrowid:04d}"
    def _id(self,lid):
        s=str(lid).strip().upper(); return int(s[1:] if s.startswith("L") else s)
    def get(self,lid):
        try: n=self._id(lid)
        except Exception: return None
        with self.con() as c: r=c.execute("SELECT * FROM learnings WHERE id=?",(n,)).fetchone()
        if not r:return None
        d=dict(r); d["learning_id"]=f"L{d['id']:04d}"; return d
    def list(self,limit=50,statuses=None):
        with self.con() as c:
            if statuses:
                q=','.join('?' for _ in statuses); rows=c.execute(f"SELECT * FROM learnings WHERE status IN ({q}) ORDER BY priority DESC,updated_at DESC LIMIT ?",(*statuses,int(limit))).fetchall()
            else: rows=c.execute("SELECT * FROM learnings ORDER BY priority DESC,updated_at DESC LIMIT ?",(int(limit),)).fetchall()
        out=[]
        for r in rows:
            d=dict(r); d["learning_id"]=f"L{d['id']:04d}"; out.append(d)
        return out
    def update(self,lid,**kw):
        n=self._id(lid); allowed={"kind","source","status","scope","statement","evidence","confidence","priority"}; cols=[]; vals=[]
        for k,v in kw.items():
            if k not in allowed: continue
            if k=="status": v=str(v).upper()
            if k=="priority": v=int(v)
            elif isinstance(v,str): v=safe(v)
            cols.append(f"{k}=?"); vals.append(v)
        if not cols:return
        cols.append("updated_at=?"); vals.extend([now(),n])
        with self.con() as c: c.execute(f"UPDATE learnings SET {', '.join(cols)} WHERE id=?",vals)
    def delete(self,lid):
        with self.con() as c: c.execute("DELETE FROM learnings WHERE id=?",(self._id(lid),))
    def has_run(self,rid):
        with self.con() as c:return bool(c.execute("SELECT 1 FROM learnings WHERE run_id=? LIMIT 1",(rid,)).fetchone())

LEARNING=LearningStore()
