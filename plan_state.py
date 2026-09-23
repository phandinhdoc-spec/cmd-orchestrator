from __future__ import annotations
import json,os
from .db_common import LOCK,con,now,safe

class PlanStateMixin:
    def init_plan_state(self):
        with con() as c:c.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(run_id TEXT NOT NULL,task_id TEXT NOT NULL,title TEXT,description TEXT,dependencies TEXT,
          task_class TEXT,risk TEXT,provider TEXT,model TEXT,reasoning TEXT,executor TEXT,status TEXT NOT NULL,verification TEXT,
          attempts INTEGER DEFAULT 0,files_touched TEXT,output_summary TEXT,last_error TEXT,started_at TEXT,completed_at TEXT,updated_at TEXT NOT NULL,
          PRIMARY KEY(run_id,task_id),FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS work_units(run_id TEXT NOT NULL,unit_id TEXT NOT NULL,task_id TEXT NOT NULL,title TEXT,description TEXT,
          dependencies TEXT,task_class TEXT,risk TEXT,hermes_provider TEXT,hermes_model TEXT,hermes_reasoning TEXT,provider TEXT,model TEXT,
          reasoning TEXT,route_source TEXT DEFAULT 'hermes',executor TEXT,status TEXT NOT NULL,verification TEXT,attempts INTEGER DEFAULT 0,
          files_touched TEXT,output_summary TEXT,last_error TEXT,started_at TEXT,completed_at TEXT,updated_at TEXT NOT NULL,
          PRIMARY KEY(run_id,unit_id),FOREIGN KEY(run_id,task_id) REFERENCES tasks(run_id,task_id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS steps(run_id TEXT NOT NULL,step_id TEXT NOT NULL,unit_id TEXT NOT NULL,ordinal INTEGER DEFAULT 0,
          title TEXT,description TEXT,status TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(run_id,step_id),
          FOREIGN KEY(run_id,unit_id) REFERENCES work_units(run_id,unit_id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_units_run ON work_units(run_id,status);
        """)
    def set_plan(self,rid,plan):
        t=now(); tasks=plan.get("tasks",[])
        with LOCK,con() as c:
            c.execute("DELETE FROM steps WHERE run_id=?",(rid,)); c.execute("DELETE FROM work_units WHERE run_id=?",(rid,)); c.execute("DELETE FROM tasks WHERE run_id=?",(rid,))
            c.execute("UPDATE runs SET plan_json=?,status='PLANNED',current_stage='review',review_state='PENDING',updated_at=? WHERE run_id=?",(json.dumps(plan,ensure_ascii=False),t,rid))
            for ti,task in enumerate(tasks,1):
                tid=str(task.get("id") or f"T{ti}")
                c.execute("""INSERT INTO tasks(run_id,task_id,title,description,dependencies,task_class,risk,status,verification,attempts,files_touched,output_summary,last_error,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,tid,safe(task.get("title"),300),safe(task.get("description")),json.dumps(task.get("dependencies",[]),ensure_ascii=False),safe(task.get("task_class","general"),80),safe(task.get("risk","medium"),20),"READY",safe(task.get("verification",""),1000),0,"[]","","",t))
                for ui,u in enumerate(task.get("work_units") or [],1):
                    uid=str(u.get("id") or f"W{ti}.{ui}"); hp=safe(u.get("provider",""),80); hm=safe(u.get("model",""),160); hr=safe(u.get("reasoning","Hermes route"),2000)
                    c.execute("""INSERT INTO work_units(run_id,unit_id,task_id,title,description,dependencies,task_class,risk,hermes_provider,hermes_model,hermes_reasoning,provider,model,reasoning,route_source,status,verification,attempts,files_touched,output_summary,last_error,updated_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,uid,tid,safe(u.get("title"),300),safe(u.get("description")),json.dumps(u.get("dependencies",[]),ensure_ascii=False),safe(u.get("task_class","general"),80),safe(u.get("risk","medium"),20),hp,hm,hr,hp,hm,hr,"hermes","READY",safe(u.get("verification",""),1000),0,"[]","","",t))
                    for si,s in enumerate(u.get("steps") or [],1):
                        sid=str(s.get("id") or f"S{ti}.{ui}.{si}"); c.execute("INSERT INTO steps(run_id,step_id,unit_id,ordinal,title,description,status,updated_at) VALUES(?,?,?,?,?,?,?,?)",(rid,sid,uid,si,safe(s.get("title"),300),safe(s.get("description")),"PENDING",t))
        self.refresh_counts(rid); self.checkpoint(rid,"hermes_plan_captured",{"tasks":len(tasks),"work_units":len(self.work_units(rid))})
    def _update(self,table,idcol,rid,item,allowed,kw):
        cols=[]; vals=[]
        for k,v in kw.items():
            if k not in allowed:continue
            if k in {"dependencies","files_touched"} and not isinstance(v,str):v=json.dumps(v,ensure_ascii=False)
            if isinstance(v,str):v=safe(v)
            cols.append(f"{k}=?"); vals.append(v)
        if not cols:return
        cols.append("updated_at=?"); vals.append(now()); vals.extend([rid,item])
        with LOCK,con() as c:
            c.execute(f"UPDATE {table} SET {', '.join(cols)} WHERE run_id=? AND {idcol}=?",vals)
            c.execute("UPDATE runs SET current_task=?,updated_at=?,process_id=? WHERE run_id=?",(item,now(),os.getpid(),rid))
        self.refresh_counts(rid); self.checkpoint(rid,"item_update",{"id":item,**{k:v for k,v in kw.items() if k in ("status","provider","model","route_source")}},item)
    def update_task(self,rid,tid,**kw): self._update("tasks","task_id",rid,tid,{"title","description","dependencies","task_class","risk","status","verification","attempts","files_touched","output_summary","last_error","started_at","completed_at"},kw)
    def update_unit(self,rid,uid,**kw): self._update("work_units","unit_id",rid,uid,{"title","description","dependencies","task_class","risk","provider","model","reasoning","route_source","executor","status","verification","attempts","files_touched","output_summary","last_error","started_at","completed_at"},kw)
    def update_step(self,rid,sid,status=None):
        if status is not None:
            with LOCK,con() as c:c.execute("UPDATE steps SET status=?,updated_at=? WHERE run_id=? AND step_id=?",(safe(status,24),now(),rid,sid))
    def reset_unit_to_hermes(self,rid,uid):
        u=self.unit(rid,uid)
        if not u:raise ValueError(f"unknown work unit: {uid}")
        self.update_unit(rid,uid,provider=u.get("hermes_provider") or "",model=u.get("hermes_model") or "",reasoning=u.get("hermes_reasoning") or "Hermes route",route_source="hermes")
    def task(self,rid,tid):
        with con() as c:r=c.execute("SELECT * FROM tasks WHERE run_id=? AND task_id=?",(rid,tid)).fetchone(); return dict(r) if r else None
    def unit(self,rid,uid):
        with con() as c:r=c.execute("SELECT * FROM work_units WHERE run_id=? AND unit_id=?",(rid,uid)).fetchone(); return dict(r) if r else None
    def tasks(self,rid):
        with con() as c:rows=[dict(r) for r in c.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY task_id",(rid,)).fetchall()]
        for x in rows:
            try:x["dependencies"]=json.loads(x.get("dependencies") or "[]")
            except Exception:x["dependencies"]=[]
        return rows
    def work_units(self,rid):
        with con() as c:rows=[dict(r) for r in c.execute("SELECT * FROM work_units WHERE run_id=? ORDER BY unit_id",(rid,)).fetchall()]
        for x in rows:
            try:x["dependencies"]=json.loads(x.get("dependencies") or "[]")
            except Exception:x["dependencies"]=[]
        return rows
    def steps(self,rid,uid=None):
        with con() as c:
            q=c.execute("SELECT * FROM steps WHERE run_id=? AND unit_id=? ORDER BY ordinal,step_id",(rid,uid)).fetchall() if uid else c.execute("SELECT * FROM steps WHERE run_id=? ORDER BY unit_id,ordinal,step_id",(rid,)).fetchall()
            return [dict(r) for r in q]
    def plan_tree(self,rid):
        tasks=self.tasks(rid); sm={}; um={}
        for s in self.steps(rid):sm.setdefault(s["unit_id"],[]).append(s)
        for u in self.work_units(rid):u["steps"]=sm.get(u["unit_id"],[]); um.setdefault(u["task_id"],[]).append(u)
        for t in tasks:
            t["work_units"]=um.get(t["task_id"],[]); st=[u.get("status") for u in t["work_units"]]
            if st:t["status"]="DONE" if all(x in ("DONE","SKIPPED") for x in st) else "FAILED" if any(x=="FAILED" for x in st) else "RUNNING" if any(x=="RUNNING" for x in st) else "READY"
        return tasks
    def refresh_counts(self,rid):
        with con() as c:
            rows=c.execute("SELECT status,COUNT(*) n FROM work_units WHERE run_id=? GROUP BY status",(rid,)).fetchall() or c.execute("SELECT status,COUNT(*) n FROM tasks WHERE run_id=? GROUP BY status",(rid,)).fetchall()
            m={r["status"]:r["n"] for r in rows}; total=sum(m.values()); done=m.get("DONE",0); failed=m.get("FAILED",0)
            c.execute("UPDATE runs SET total_tasks=?,completed_tasks=?,failed_tasks=?,pending_tasks=?,updated_at=? WHERE run_id=?",(total,done,failed,total-done-failed,now(),rid))
