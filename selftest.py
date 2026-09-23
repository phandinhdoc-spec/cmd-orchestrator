#!/usr/bin/env python3
from __future__ import annotations
import os, subprocess, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
code=r"""
import sys,os
sys.path.insert(0,os.environ["PARENT"])
import importlib
pkg=importlib.import_module("cmd-orchestrator-v1.0.0".replace("-","_"))
"""
# We test modules by copying them to a valid package name in isolated HOME.
with tempfile.TemporaryDirectory() as td:
    home=Path(td)/"home"; home.mkdir()
    pkg=Path(td)/"cmd_orchestrator"; pkg.mkdir()
    for p in HERE.glob("*.py"):
        if p.name in ("selftest.py","install.py"): continue
        (pkg/p.name).write_bytes(p.read_bytes())
    script=r"""
import os,sys,json
sys.path.insert(0,os.environ["TD"])
import cmd_orchestrator.config as cfg
from cmd_orchestrator.storage import STORE
from cmd_orchestrator.engine import orchestrate
from cmd_orchestrator.commands import fmt_status
x=orchestrate("test multi file project",project="SELFTEST",repository="local")
rid=x["run_id"]
assert STORE.run(rid)["total_tasks"]>=1
STORE.update_task(rid,"T1",status="DONE",verification="PASS")
STORE.set_run(rid,status="INTERRUPTED")
r=STORE.resume(rid)
assert r["status"]=="RUNNING"
assert "CMD ORCHESTRATOR v1.0.0" in fmt_status(True)
print("SELFTEST PASS",rid)
"""
    env=os.environ.copy(); env["HOME"]=str(home); env["TD"]=td
    cp=subprocess.run([sys.executable,"-c",script],env=env,text=True,capture_output=True)
    print(cp.stdout,end="")
    if cp.returncode:
        print(cp.stderr,file=sys.stderr); raise SystemExit(cp.returncode)
