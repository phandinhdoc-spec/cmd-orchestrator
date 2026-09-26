from __future__ import annotations
import os, subprocess
from shutil import which

class CommandCodeError(RuntimeError): pass

def executable() -> str:
    # Official CLI binary is "cmd". Override only when necessary.
    return os.environ.get("COMMANDCODE_BIN", "cmd")

def invoke(prompt: str, model: str = "", cwd: str = "", timeout: int = 1800,
           effort: str = "", permission_mode: str = "yolo") -> str:
    """Run an isolated, non-interactive Command Code worker."""
    argv=[executable(), "-p", prompt, "--no-session", "--skip-onboarding"]
    if model:
        argv += ["--model", model]
    if effort:
        argv += ["--effort", effort]
    if permission_mode:
        argv += ["--permission-mode", permission_mode]
    cp=subprocess.run(argv,cwd=cwd or None,text=True,capture_output=True,timeout=timeout)
    if cp.returncode:
        raise CommandCodeError(
            f"Command Code exit={cp.returncode}: {(cp.stderr or cp.stdout)[-4000:]}"
        )
    return cp.stdout

def available() -> bool:
    return which(executable()) is not None

def list_models(timeout: int = 60) -> str:
    cp=subprocess.run([executable(),"--list-models"],text=True,capture_output=True,timeout=timeout)
    if cp.returncode:
        raise CommandCodeError(f"Cannot list models: {(cp.stderr or cp.stdout)[-4000:]}")
    return cp.stdout
