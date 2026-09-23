from __future__ import annotations
import json, shutil
from pathlib import Path
from .config import STATE_ROOT, RUNS_DIR, CURRENT_JSON, RUN_DB, LEARN_DB, SETTINGS_JSON, RESCUE_DIR
from .storage import STORE
from .learning_store import LEARNING

MARKER = "# cmd-orchestrator v"
PROJECT_FILES = (
    ".ai/task_on_progress.md",
)

def _safe_cmd_file(path: Path) -> bool:
    """Never delete an arbitrary project file: require a known path and CMD marker."""
    try:
        if not path.is_file():
            return False
        if path.as_posix().endswith(".ai/task_on_progress.md"):
            return MARKER in path.read_text(encoding="utf-8", errors="ignore")[:300]
    except Exception:
        return False
    return False

def _project_root() -> Path:
    p=Path.cwd().resolve()
    for root in (p,*p.parents):
        if (root/".git").exists() or (root/".ai").exists():
            return root
    return p

def project_candidates(root=None):
    root=Path(root).resolve() if root else _project_root()
    out=[]
    for rel in PROJECT_FILES:
        p=root/rel
        if _safe_cmd_file(p):
            out.append({"id":f"P{len(out)+1}","path":str(p),"kind":"project_artifact"})
    return out

def state_candidates():
    out=[]
    if RUNS_DIR.exists():
        for p in sorted(RUNS_DIR.glob("run_*.json")):
            out.append({"id":f"S{len(out)+1}","path":str(p),"kind":"run_snapshot"})
    if RESCUE_DIR.exists():
        for p in sorted(RESCUE_DIR.glob("*")):
            if p.is_file():
                out.append({"id":f"S{len(out)+1}","path":str(p),"kind":"rescue_artifact"})
    return out

def preview(scope="select", deep=False):
    scope=(scope or "select").lower()
    items=project_candidates()
    if scope=="all" or deep:
        items += state_candidates()
    return {
        "scope":scope,
        "deep":bool(deep),
        "project_root":str(_project_root()),
        "items":items,
        "protected":[
            str(LEARN_DB)+" (learning is preserved; use --learning explicitly)",
            str(SETTINGS_JSON)+" (settings preserved)",
            "plugin source/install files (never touched)",
        ],
    }

def _unlink(path):
    p=Path(path)
    try:
        p.unlink()
        return True
    except FileNotFoundError:
        return False

def clean_selected(ids):
    wanted={x.upper() for x in ids}
    candidates=preview("all",True)["items"]
    chosen=[x for x in candidates if x["id"].upper() in wanted]
    deleted=[]
    for x in chosen:
        if x["kind"]=="project_artifact" and not _safe_cmd_file(Path(x["path"])):
            continue
        if _unlink(x["path"]):
            deleted.append(x["path"])
    return {"mode":"select","deleted":deleted,"count":len(deleted)}

def clean_project(deep=False):
    root=_project_root()
    deleted=[]
    for x in project_candidates(root):
        if _unlink(x["path"]): deleted.append(x["path"])
    # Deep project cleanup removes CMD run snapshots associated with the current
    # repository/project when identifiable, but never user source files.
    if deep:
        root_s=str(root)
        for r in STORE.history(10000):
            repo=str(r.get("repository") or "")
            project=str(r.get("project") or "")
            if root_s in repo or repo in root_s or project==root.name:
                snap=RUNS_DIR/f"{r['run_id']}.json"
                if _unlink(snap): deleted.append(str(snap))
    return {"mode":"project","deep":bool(deep),"project_root":str(root),"deleted":deleted,"count":len(deleted)}

def clean_all(deep=False, learning=False):
    deleted=[]
    # Known project artifact in the current project.
    for x in project_candidates():
        if _unlink(x["path"]): deleted.append(x["path"])
    # All historical CMD file artifacts.
    for x in state_candidates():
        if _unlink(x["path"]): deleted.append(x["path"])
    if deep:
        # Deep means reset CMD runtime state files/databases. Settings stay so
        # provider/user configuration is not unexpectedly lost.
        for p in (CURRENT_JSON,RUN_DB):
            if _unlink(p): deleted.append(str(p))
        for suffix in ("-wal","-shm"):
            p=Path(str(RUN_DB)+suffix)
            if _unlink(p): deleted.append(str(p))
        if learning:
            for p in (LEARN_DB,Path(str(LEARN_DB)+"-wal"),Path(str(LEARN_DB)+"-shm")):
                if _unlink(p): deleted.append(str(p))
        # Keep the currently loaded Hermes process usable after a deep reset:
        # recreate empty schemas, not historical data.
        STORE.init_run_state()
        STORE.init_plan_state()
        if learning:
            LEARNING.init()
    return {"mode":"all","deep":bool(deep),"learning":bool(learning),"deleted":deleted,"count":len(deleted),
            "note":"deep reset completed; empty runtime databases were reinitialized so Hermes can continue without restart" if deep else ""}

def format_preview(data):
    lines=[f"CMD CLEAN PREVIEW  mode={data['scope']} deep={str(data['deep']).lower()}",
           f"project = {data['project_root']}",""]
    if not data["items"]:
        lines.append("(no CMD-generated files found)")
    else:
        for x in data["items"]:
            lines.append(f"{x['id']:<4} {x['kind']:<18} {x['path']}")
    lines += ["","Protected by default:"]
    lines += [f"  - {x}" for x in data["protected"]]
    return "\n".join(lines)
