from __future__ import annotations
import os, shlex, subprocess, tempfile
from pathlib import Path

class CommandCodeError(RuntimeError): pass

def executable() -> str:
    return os.environ.get("COMMANDCODE_BIN", "commandcode")

def invoke(prompt: str, model: str = "", cwd: str = "", timeout: int = 1800) -> str:
    """Run one isolated CommandCode worker.

    COMMANDCODE_ARGS is intentionally configurable because CommandCode CLI builds
    may expose different flags. Placeholders: {model}, {prompt_file}.
    Default: run the binary with the prompt on stdin and optional --model.
    """
    exe=executable()
    args_tpl=os.environ.get("COMMANDCODE_ARGS","").strip()
    if args_tpl:
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",suffix=".md",delete=False) as f:
            f.write(prompt); prompt_file=f.name
        try:
            rendered=args_tpl.format(model=model,prompt_file=prompt_file)
            argv=[exe,*shlex.split(rendered)]
            cp=subprocess.run(argv,cwd=cwd or None,text=True,capture_output=True,timeout=timeout)
        finally:
            Path(prompt_file).unlink(missing_ok=True)
    else:
        argv=[exe]
        if model: argv += ["--model",model]
        cp=subprocess.run(argv,input=prompt,cwd=cwd or None,text=True,capture_output=True,timeout=timeout)
    if cp.returncode:
        raise CommandCodeError(f"CommandCode exit={cp.returncode}: {cp.stderr[-4000:]}")
    return cp.stdout

def available() -> bool:
    from shutil import which
    return which(executable()) is not None
