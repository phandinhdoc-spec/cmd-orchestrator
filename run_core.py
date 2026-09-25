from __future__ import annotations
import json,os,time,uuid
from .config import VERSION,CURRENT_JSON
from .db_common import LOCK,con,now,safe,pid_alive

class RunCoreMixin:
    def init_run_state(self):
        with con() as c:c.executescript("""
        CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,project TEXT,repository TEXT,request TEXT,status TEXT NOT NULL,
          mode TEXT,auto_mode TEXT,current_stage TEXT,current_task TEXT,total_tasks INTEGER DEFAULT 0,completed_tasks INTEGER DEFAULT 0,
          failed_tasks INTEGER DEFAULT 0,pending_tasks INTEGER DEFAULT 0,process_id INTEGER,session_id TEXT,plan_json TEXT,
          review_state TEXT DEFAULT 'PENDING',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_checkpoint_reason TEXT,last_error TEXT);
        CREATE TABLE IF NOT EXISTS prompts(run_id TEXT PRIMARY KEY,original_prompt TEXT,grilled_prompt TEXT,selected_prompt TEXT,
          selection TEXT,status TEXT NOT NULL DEFAULT 'PENDING',updated_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS checkpoints(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,task_id TEXT,event TEXT NOT NULL,payload TEXT,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at DESC);
        """)
    def create_run(self,request,project="",repository="",mode="balanced",auto_mode="review",session_id=""):
        rid=f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"; t=now()
        with LOCK,con() as c:c.execute("""INSERT INTO runs(run_id,project,repository,request,status,mode,auto_mode,current_stage,process_id,session_id,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,safe(project,256),safe(repository,1024),safe(request),"PROMPT_REVIEW",mode,auto_mode,"prompt_review",os.getpid(),safe(session_id,256),t,t))
        self.checkpoint(rid,"run_created",{"version":VERSION,"owner":"cmd_control_plane","runtime":"hermes"}); return rid
    def set_prompt(self,rid,original,grilled=""):
        t=now()
        with LOCK,con() as c:
            c.execute("""INSERT INTO prompts(run_id,original_prompt,grilled_prompt,selected_prompt,selection,status,updated_at) VALUES(?,?,?,?,?,?,?)
              ON CONFLICT(run_id) DO UPDATE SET original_prompt=excluded.original_prompt,grilled_prompt=excluded.grilled_prompt,status='PENDING',updated_at=excluded.updated_at""",
              (rid,safe(original),safe(grilled),"","","PENDING",t))
            c.execute("UPDATE runs SET request=?,status='PLANNING',current_stage='planning_l1',review_state='PENDING',updated_at=? WHERE run_id=?",(safe(original),t,rid))
        self.checkpoint(rid,"prompt_captured",{"has_grilled":bool(grilled)})
    def prompt(self,rid):
        with con() as c:r=c.execute("SELECT * FROM prompts WHERE run_id=?",(rid,)).fetchone(); return dict(r) if r else None
    def select_prompt(self,rid,selection,edited=""):
        p=self.prompt(rid)
        if not p:raise ValueError("prompt review not found")
        sel=(selection or "").lower().strip()
        if sel=="original":chosen=p.get("original_prompt") or ""
        elif sel=="grilled":chosen=p.get("grilled_prompt") or p.get("original_prompt") or ""
        elif sel=="edited" and edited.strip():chosen=edited
        else:raise ValueError("selection must be original, grilled, or edited with text")
        with LOCK,con() as c:
            c.execute("UPDATE prompts SET selected_prompt=?,selection=?,status='SELECTED',updated_at=? WHERE run_id=?",(safe(chosen),sel,now(),rid))
            c.execute("UPDATE runs SET status='PLANNING',current_stage='hermes_plan',review_state='PENDING',updated_at=? WHERE run_id=?",(now(),rid))
        self.checkpoint(rid,"prompt_selected",{"selection":sel}); return chosen
    def run(self,rid):
        with con() as c:r=c.execute("SELECT * FROM runs WHERE run_id=?",(rid,)).fetchone(); return dict(r) if r else None
    def current(self):
        try:
            if CURRENT_JSON.exists():
                rid=json.loads(CURRENT_JSON.read_text(encoding="utf-8")).get("run_id")
                if rid and self.run(rid):return self.run(rid)
        except Exception:pass
        with con() as c:r=c.execute("SELECT * FROM runs ORDER BY updated_at DESC LIMIT 1").fetchone(); return dict(r) if r else None
    def set_run(self,rid,status=None,stage=None,review_state=None,error=None):
        fields=[]; vals=[]
        for col,val in (("status",status),("current_stage",stage),("review_state",review_state),("last_error",error)):
            if val is not None:fields.append(f"{col}=?"); vals.append(safe(val,2000) if isinstance(val,str) else val)
        fields += ["updated_at=?","process_id=?"]; vals += [now(),os.getpid(),rid]
        with LOCK,con() as c:c.execute(f"UPDATE runs SET {', '.join(fields)} WHERE run_id=?",vals)
        self.snapshot(rid)
    def checkpoint(self,rid,event,payload=None,tid=""):
        t=now()
        with LOCK,con() as c:
            c.execute("INSERT INTO checkpoints(run_id,task_id,event,payload,created_at) VALUES(?,?,?,?,?)",(rid,tid or None,event,json.dumps(payload or {},ensure_ascii=False,default=str),t))
            c.execute("UPDATE runs SET updated_at=?,last_checkpoint_reason=?,process_id=? WHERE run_id=?",(t,event,os.getpid(),rid))
        self.snapshot(rid)
    def latest_cp(self,rid):
        with con() as c:r=c.execute("SELECT * FROM checkpoints WHERE run_id=? ORDER BY id DESC LIMIT 1",(rid,)).fetchone(); return dict(r) if r else None
    def recover_stale(self):
        r=self.current()
        if r and r["status"] in {"RUNNING","VERIFYING","PLANNING"} and not pid_alive(r.get("process_id")):
            with con() as c:
                c.execute("UPDATE runs SET status='INTERRUPTED',updated_at=?,last_checkpoint_reason='stale_recovery' WHERE run_id=?",(now(),r["run_id"])); c.execute("UPDATE work_units SET status='READY',updated_at=? WHERE run_id=? AND status='RUNNING'",(now(),r["run_id"]))
            self.snapshot(r["run_id"])
    def resume(self,rid=None):
        r=self.run(rid) if rid else None
        if not r:
            with con() as c:q=c.execute("SELECT * FROM runs WHERE status IN ('INTERRUPTED','PLANNED','PAUSED','FAILED') ORDER BY updated_at DESC LIMIT 1").fetchone(); r=dict(q) if q else None
        if not r:return None
        self.set_run(r["run_id"],status="RUNNING",stage="resume",review_state="APPROVED"); self.checkpoint(r["run_id"],"resume",{}); return self.run(r["run_id"])
    def history(self,n=15):
        with con() as c:return [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?",(int(n),)).fetchall()]
