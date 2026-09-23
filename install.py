#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil, time, os
from pathlib import Path

VERSION="1.0.1"
HOME=Path.home()
DST=HOME/".hermes"/"plugins"/"cmd-orchestrator"
BACK=HOME/".hermes"/"plugin-backups"
STATE=HOME/".hermes"/"state"/"cmd-orchestrator"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--clean-state",action="store_true",help="Backup and remove old orchestrator state/learning before install.")
    a=ap.parse_args()
    src=Path(__file__).resolve().parent
    BACK.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime("%Y%m%d-%H%M%S")

    if DST.exists():
        b=BACK/f"cmd-orchestrator-plugin-{stamp}"
        shutil.move(str(DST),str(b))
        print("[backup plugin]",b)

    if a.clean_state and STATE.exists():
        b=BACK/f"cmd-orchestrator-state-{stamp}"
        shutil.move(str(STATE),str(b))
        print("[backup state ]",b)

    # Critical: backup is OUTSIDE ~/.hermes/plugins so Hermes will not discover it as a duplicate plugin.
    DST.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(src,DST,ignore=shutil.ignore_patterns("__pycache__","*.pyc","install.py","selftest.py","README.md"))
    print("[installed]",DST)
    print("version 1.0.1")
    print()
    print("Reload Hermes gateway:")
    print("  hermes gateway stop")
    print("  hermes gateway start")
    print("  hermes plugins list | grep cmd-orchestrator")
    print()
    print("Then inside Hermes:")
    print("  /cmd-help")
    print("  /cmd-status")

if __name__=="__main__":
    main()
