#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
if __package__ in (None,""):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from native import plan,run,status
else:
    from .native import plan,run,status

def main():
    p=argparse.ArgumentParser(prog="cmd-orchestrator",description="CommandCode-native DAG orchestrator")
    sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("plan"); q.add_argument("request"); q.add_argument("--project",default=os.getcwd()); q.add_argument("--mode",choices=["cheap","balanced","quality","fast"],default="balanced")
    q=sub.add_parser("run"); q.add_argument("run_id",nargs="?",default=""); q.add_argument("-j","--jobs",type=int,default=3)
    q=sub.add_parser("status"); q.add_argument("run_id",nargs="?",default="")
    a=p.parse_args()
    if a.command=="plan": out=plan(a.request,a.project,a.mode)
    elif a.command=="run": out=run(a.run_id,a.jobs)
    else: out=status(a.run_id)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
