from __future__ import annotations
import json, os, sqlite3, time, uuid
from pathlib import Path
from threading import RLock
from typing import Optional
from .config import (
    VERSION, STATE_ROOT, RUN_DB, LEARN_DB, CURRENT_JSON, RUNS_DIR,
    ensure_dirs
)

LOCK = RLock()
TERMINAL = {"DONE", "FAILED", "ABORTED", "SKIPPED"}

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False

def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def safe(v, n=8000):
    s = "" if v is None else str(v)
    low = s.lower()
    if any(x in low for x in ("api_key", "authorization:", "bearer ", "password=", "secret=", "token=")):
        return "[REDACTED]"
    return s[:n]

class Store:
    def __init__(self):
        ensure_dirs()
        self.init()
        self.recover_stale()

    def con(self, db=RUN_DB):
        c = sqlite3.connect(db, timeout=5)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def init(self):
        with self.con() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS runs(
              run_id TEXT PRIMARY KEY, project TEXT, repository TEXT, request TEXT,
              status TEXT NOT NULL, mode TEXT, auto_mode TEXT,
              current_stage TEXT, current_task TEXT,
              total_tasks INTEGER DEFAULT 0, completed_tasks INTEGER DEFAULT 0,
              failed_tasks INTEGER DEFAULT 0, pending_tasks INTEGER DEFAULT 0,
              process_id INTEGER, session_id TEXT,
              plan_json TEXT, review_state TEXT DEFAULT 'PENDING',
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              last_checkpoint_reason TEXT, last_error TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks(
              run_id TEXT NOT NULL, task_id TEXT NOT NULL, title TEXT, description TEXT,
              dependencies TEXT, task_class TEXT, risk TEXT,
              provider TEXT, model TEXT, reasoning TEXT, executor TEXT,
              status TEXT NOT NULL, verification TEXT, attempts INTEGER DEFAULT 0,
              files_touched TEXT, output_summary TEXT, last_error TEXT,
              started_at TEXT, completed_at TEXT, updated_at TEXT NOT NULL,
              PRIMARY KEY(run_id,task_id),
              FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS checkpoints(
              id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              task_id TEXT, event TEXT NOT NULL, payload TEXT, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id,status);
            """)
        with self.con(LEARN_DB) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS outcomes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_class TEXT, provider TEXT, model TEXT, success INTEGER,
              verified INTEGER, attempts INTEGER, latency_ms INTEGER,
              cost_hint TEXT, error TEXT, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_outcomes_class ON outcomes(task_class,provider,model);
            """)

    def create_run(self, request, project="", repository="", mode="balanced", auto_mode="review", session_id=""):
        rid = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        t = now()
        with LOCK, self.con() as c:
            c.execute("""INSERT INTO runs(
              run_id,project,repository,request,status,mode,auto_mode,process_id,session_id,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (rid,safe(project,256),safe(repository,1024),safe(request),"PLANNING",mode,auto_mode,os.getpid(),safe(session_id,256),t,t))
        self.checkpoint(rid,"run_created",{"version":VERSION})
        return rid

    def set_plan(self, rid, plan):
        tasks = plan.get("tasks", [])
        t = now()
        with LOCK, self.con() as c:
            c.execute("""UPDATE runs SET plan_json=?, status='PLANNED', current_stage='plan',
              total_tasks=?, pending_tasks=?, updated_at=? WHERE run_id=?""",
              (json.dumps(plan,ensure_ascii=False),len(tasks),len(tasks),t,rid))
            for i, x in enumerate(tasks,1):
                tid = str(x.get("id") or f"T{i}")
                c.execute("""INSERT OR REPLACE INTO tasks(
                  run_id,task_id,title,description,dependencies,task_class,risk,status,verification,
                  attempts,files_touched,output_summary,last_error,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid,tid,safe(x.get("title"),300),safe(x.get("description")),
                 json.dumps(x.get("dependencies",[]),ensure_ascii=False),
                 safe(x.get("task_class","general"),80),safe(x.get("risk","medium"),20),
                 "PENDING",safe(x.get("verification",""),1000),0,"[]","","",t))
        self.checkpoint(rid,"plan_created",{"tasks":len(tasks)})

    def update_task(self, rid, tid, **kw):
        allowed = {"provider","model","reasoning","executor","status","verification","attempts",
                   "files_touched","output_summary","last_error","started_at","completed_at"}
        cols=[]; vals=[]
        for k,v in kw.items():
            if k not in allowed: continue
            if k=="files_touched" and not isinstance(v,str):
                v=json.dumps(v,ensure_ascii=False)
            if k in {"output_summary","last_error","executor","provider","model","reasoning","verification"}:
                v=safe(v)
            cols.append(f"{k}=?"); vals.append(v)
        if not cols: return
        cols.append("updated_at=?"); vals.append(now())
        vals += [rid,tid]
        with LOCK, self.con() as c:
            c.execute(f"UPDATE tasks SET {', '.join(cols)} WHERE run_id=? AND task_id=?", vals)
            c.execute("UPDATE runs SET current_task=?,updated_at=?,process_id=? WHERE run_id=?",
                      (tid,now(),os.getpid(),rid))
        self.refresh_counts(rid)
        self.checkpoint(rid,"task_update",{"task_id":tid,**{k:v for k,v in kw.items() if k in ("status","provider","model")}},tid)

    def set_run(self, rid, status=None, stage=None, review_state=None, error=None):
        fields=[]; vals=[]
        if status is not None: fields.append("status=?"); vals.append(status)
        if stage is not None: fields.append("current_stage=?"); vals.append(stage)
        if review_state is not None: fields.append("review_state=?"); vals.append(review_state)
        if error is not None: fields.append("last_error=?"); vals.append(safe(error,2000))
        fields += ["updated_at=?","process_id=?"]; vals += [now(),os.getpid(),rid]
        with LOCK, self.con() as c:
            c.execute(f"UPDATE runs SET {', '.join(fields)} WHERE run_id=?", vals)
        self.snapshot(rid)

    def checkpoint(self, rid, event, payload=None, tid=""):
        payload = payload or {}
        t=now()
        with LOCK, self.con() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO checkpoints(run_id,task_id,event,payload,created_at) VALUES(?,?,?,?,?)",
                      (rid,tid or None,event,json.dumps(payload,ensure_ascii=False,default=str),t))
            c.execute("UPDATE runs SET updated_at=?,last_checkpoint_reason=?,process_id=? WHERE run_id=?",
                      (t,event,os.getpid(),rid))
            c.commit()
        self.snapshot(rid)

    def refresh_counts(self,rid):
        with self.con() as c:
            rows=c.execute("SELECT status,COUNT(*) n FROM tasks WHERE run_id=? GROUP BY status",(rid,)).fetchall()
            m={r["status"]:r["n"] for r in rows}; total=sum(m.values())
            done=m.get("DONE",0); failed=m.get("FAILED",0); pending=total-done-failed
            c.execute("UPDATE runs SET total_tasks=?,completed_tasks=?,failed_tasks=?,pending_tasks=?,updated_at=? WHERE run_id=?",
                      (total,done,failed,pending,now(),rid))

    def run(self,rid):
        with self.con() as c:
            r=c.execute("SELECT * FROM runs WHERE run_id=?",(rid,)).fetchone()
            return dict(r) if r else None

    def current(self):
        try:
            if CURRENT_JSON.exists():
                rid=json.loads(CURRENT_JSON.read_text(encoding="utf-8")).get("run_id")
                if rid and self.run(rid): return self.run(rid)
        except Exception: pass
        with self.con() as c:
            r=c.execute("SELECT * FROM runs ORDER BY updated_at DESC LIMIT 1").fetchone()
            return dict(r) if r else None

    def tasks(self,rid):
        with self.con() as c:
            return [dict(r) for r in c.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY task_id",(rid,)).fetchall()]

    def latest_cp(self,rid):
        with self.con() as c:
            r=c.execute("SELECT * FROM checkpoints WHERE run_id=? ORDER BY id DESC LIMIT 1",(rid,)).fetchone()
            return dict(r) if r else None

    def snapshot(self,rid):
        r=self.run(rid)
        if not r: return
        data={"version":VERSION,"run":r,"tasks":self.tasks(rid),"latest_checkpoint":self.latest_cp(rid)}
        atomic_json(CURRENT_JSON,{"run_id":rid,"updated_at":now()})
        atomic_json(RUNS_DIR/f"{rid}.json",data)
        try:
            cwd=Path.cwd()
            if (cwd/".git").exists() or (cwd/".ai").exists():
                ai=cwd/".ai"; ai.mkdir(exist_ok=True)
                done=[t["task_id"] for t in data["tasks"] if t["status"]=="DONE"]
                active=[t["task_id"] for t in data["tasks"] if t["status"] not in TERMINAL]
                (ai/"task_on_progress.md").write_text(
                    f"""# cmd-orchestrator v{VERSION} checkpoint

- RUN ID: {rid}
- STATUS: {r.get('status')}
- MODE: {r.get('mode')}
- AUTO: {r.get('auto_mode')}
- STAGE: {r.get('current_stage') or '-'}
- CURRENT TASK: {r.get('current_task') or '-'}
- PROGRESS: {r.get('completed_tasks',0)}/{r.get('total_tasks',0)}
- DONE: {', '.join(done) if done else '-'}
- ACTIVE/PENDING: {', '.join(active) if active else '-'}
- REVIEW: {r.get('review_state') or '-'}
- LAST CHECKPOINT: {(data['latest_checkpoint'] or {}).get('created_at',r.get('updated_at'))}
- REASON: {(data['latest_checkpoint'] or {}).get('event',r.get('last_checkpoint_reason'))}
- ERROR: {r.get('last_error') or '-'}
""",encoding="utf-8")
        except Exception: pass

    def recover_stale(self):
        r=self.current()
        if not r: return
        if r["status"] in {"RUNNING","VERIFYING","PLANNING"} and not pid_alive(r.get("process_id")):
            with self.con() as c:
                c.execute("UPDATE runs SET status='INTERRUPTED',updated_at=?,last_checkpoint_reason='stale_recovery' WHERE run_id=?",(now(),r["run_id"]))
                c.execute("UPDATE tasks SET status='READY',updated_at=? WHERE run_id=? AND status='RUNNING'",(now(),r["run_id"]))
            self.snapshot(r["run_id"])

    def resume(self,rid=None):
        if rid:
            r=self.run(rid)
        else:
            with self.con() as c:
                q=c.execute("""SELECT * FROM runs WHERE status IN ('INTERRUPTED','PLANNED','PAUSED','FAILED')
                               ORDER BY updated_at DESC LIMIT 1""").fetchone()
                r=dict(q) if q else None
        if not r: return None
        self.set_run(r["run_id"],status="RUNNING",stage="resume")
        self.checkpoint(r["run_id"],"resume",{})
        return self.run(r["run_id"])

    def history(self,n=15):
        with self.con() as c:
            return [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?",(int(n),)).fetchall()]

    def record_outcome(self,task_class,provider,model,success,verified,attempts=1,latency_ms=0,cost_hint="",error=""):
        with self.con(LEARN_DB) as c:
            c.execute("""INSERT INTO outcomes(task_class,provider,model,success,verified,attempts,latency_ms,cost_hint,error,created_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?)""",
                      (safe(task_class,80),safe(provider,80),safe(model,160),int(bool(success)),int(bool(verified)),
                       int(attempts),int(latency_ms or 0),safe(cost_hint,40),safe(error,1000),now()))

    def learning_stats(self,limit=30):
        with self.con(LEARN_DB) as c:
            return [dict(r) for r in c.execute("""
              SELECT task_class,provider,model,COUNT(*) n,
                     SUM(success) success_n,SUM(verified) verified_n,
                     ROUND(AVG(latency_ms),1) avg_latency_ms
              FROM outcomes GROUP BY task_class,provider,model
              ORDER BY n DESC LIMIT ?
            """,(int(limit),)).fetchall()]

STORE=Store()
