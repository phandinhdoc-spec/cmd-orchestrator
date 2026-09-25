#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

with tempfile.TemporaryDirectory() as td:
    home=Path(td)/"home"; home.mkdir()
    pkg=Path(td)/"cmd_orchestrator"; pkg.mkdir()
    for p in HERE.glob("*.py"):
        if p.name in ("selftest.py","install.py"): continue
        (pkg/p.name).write_bytes(p.read_bytes())
    script=r'''
import os,sys
sys.path.insert(0,os.environ["TD"])
from cmd_orchestrator.config import VERSION
from cmd_orchestrator.storage import STORE
from cmd_orchestrator.engine import begin_prompt_review,select_prompt,capture_hermes_plan,approve_run,update_work_unit,complete_run,work_packet
from cmd_orchestrator.scheduler import ready_frontier
from cmd_orchestrator.dsl import render_plan

assert VERSION=="1.4.0"
x=begin_prompt_review("write feature","GRILLED: write feature with tests",project="SELFTEST")
rid=x["run_id"]
assert STORE.prompt(rid)["status"]=="PENDING"
select_prompt("grilled",run_id=rid)
plan={"summary":"feature","tasks":[
 {"id":"T1","title":"Design","description":"design interfaces","dependencies":[],"work_units":[
   {"id":"W1.0","title":"Library discovery","description":"inspect dependencies and reusable APIs","dependencies":[],"task_class":"library_discovery","risk":"low","provider":"commandcode","model":"luna","reasoning":"cheap discovery","verification":"dependency evidence","steps":[{"id":"S1.0.1","title":"inspect dependencies"},{"id":"S1.0.2","title":"record reuse decision"}]},
   {"id":"W1.1","title":"Interface design","description":"define contract","dependencies":["W1.0"],"task_class":"design","risk":"medium","provider":"commandcode","model":"terra","reasoning":"Hermes selected balanced model","verification":"contract reviewed","steps":[{"id":"S1.1.1","title":"inspect"},{"id":"S1.1.2","title":"define interfaces"}]}
 ]},
 {"id":"T2","title":"Implementation","description":"mixed difficulty","dependencies":["T1"],"work_units":[
   {"id":"W2.1","title":"Implement helper_a","description":"one atomic helper","dependencies":["W1.0","W1.1"],"task_class":"implementation","symbol":"helper_a","library_evidence":"project and standard APIs checked; custom project logic required","files":["feature.py"],"risk":"low","provider":"commandcode","model":"luna","reasoning":"Hermes selected cheap model","verification":"unit tests","steps":[{"id":"S2.1.1","title":"implement helper_a"},{"id":"S2.1.2","title":"test helper_a"}]},
   {"id":"W2.2","title":"Implement transition","description":"state transition function","dependencies":["W1.0","W1.1"],"task_class":"algorithm","symbol":"transition","library_evidence":"state library checked; project-specific transition required","files":["state.py"],"risk":"high","provider":"commandcode","model":"sol","reasoning":"Hermes selected strong model","verification":"edge tests","steps":[{"id":"S2.2.1","title":"implement transition"},{"id":"S2.2.2","title":"edge cases"}]}
 ]}
]}
y=capture_hermes_plan(plan,rid)
assert not y["quality"]["needs_expansion"], y

# Invalid DAGs must be rejected for expansion instead of reaching the scheduler.
bad_cycle={"summary":"cycle","tasks":[{"id":"TC","title":"Cycle","work_units":[
 {"id":"WC.1","title":"A","dependencies":["WC.2"],"task_class":"design","steps":[{"title":"a"}]},
 {"id":"WC.2","title":"B","dependencies":["WC.1"],"task_class":"design","steps":[{"title":"b"}]}
]}]}
from cmd_orchestrator.planner import normalize_plan
_,bad_quality=normalize_plan(bad_cycle)
assert bad_quality["needs_expansion"] and any("dependency cycle:" in x for x in bad_quality["issues"]), bad_quality

bad_missing={"summary":"missing","tasks":[{"id":"TM","title":"Missing","work_units":[
 {"id":"WM.1","title":"A","dependencies":["DOES_NOT_EXIST"],"task_class":"design","steps":[{"title":"a"}]}
]}]}
_,missing_quality=normalize_plan(bad_missing)
assert missing_quality["needs_expansion"] and any("unknown dependency" in x for x in missing_quality["issues"]), missing_quality
assert len(STORE.work_units(rid))==4
assert "work_unit W2.2" in render_plan(STORE.plan_tree(rid),STORE.run(rid))
STORE.update_unit(rid,"W2.1",provider="manual",model="cheap",route_source="operator")
STORE.reset_unit_to_hermes(rid,"W2.1")
assert STORE.unit(rid,"W2.1")["model"]=="luna"
approve_run(rid)
front=ready_frontier(rid)
assert [u["unit_id"] for u in front["ready"]]==["W1.0"], front
update_work_unit("W1.0",status="DONE",verification="PASS",run_id=rid)
front=ready_frontier(rid)
assert [u["unit_id"] for u in front["ready"]]==["W1.1"], front
update_work_unit("W1.1",status="DONE",verification="PASS",run_id=rid)
front=ready_frontier(rid)
assert {u["unit_id"] for u in front["ready"]}=={"W2.1","W2.2"}, front
packet=work_packet("W2.1",rid)
assert packet["unit_id"]=="W2.1" and "Do not reread" in packet["instruction"], packet
update_work_unit("W2.1",status="DONE",verification="PASS",output_summary="helper complete",files_touched=["feature.py"],run_id=rid)
checked=work_packet("W2.1",rid)
assert checked["immutable"] and checked["status"]=="DONE", checked
try:
    update_work_unit("W2.1",status="RUNNING",run_id=rid)
    raise AssertionError("DONE unit reopened without explicit replan")
except ValueError as e:
    assert "immutable" in str(e)
update_work_unit("W2.2",status="DONE",verification="PASS",run_id=rid)
complete_run(True,"ok",rid)
lid=STORE.add_learning("Use focused search before broad scans",kind="rule",source="user",status="ACTIVE",confidence="high")
assert STORE.learning(lid)["status"]=="ACTIVE"
print("SELFTEST PASS",rid,lid)
'''
    env=os.environ.copy(); env["HOME"]=str(home); env["TD"]=td
    cp=subprocess.run([sys.executable,"-c",script],env=env,text=True,capture_output=True)
    print(cp.stdout,end="")
    if cp.returncode:
        print(cp.stderr,file=sys.stderr); raise SystemExit(cp.returncode)
