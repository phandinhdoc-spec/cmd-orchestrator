from __future__ import annotations
from .config import load_settings
from .storage import STORE

HIGH = ("architecture","security","permission","concurrency","migration","debug khó","thuật toán","algorithm","critical")
CHEAP = ("rename","format","grep","find","text","docs","markdown","comment","simple","inspect")

def route(task: str, task_class="general", risk="medium", mode=None):
    st=load_settings(); mode=mode or st.get("mode","balanced")
    s=(task+" "+task_class+" "+risk).lower()
    tier="balanced"
    reason="default balanced routing"
    if mode=="quality" or risk=="high" or any(x in s for x in HIGH):
        tier="strong"; reason="high-risk/complex task"
    elif mode=="cheap" or any(x in s for x in CHEAP):
        tier="cheap_fast"; reason="mechanical/low-risk task"
    elif mode=="fast":
        tier="cheap_fast"; reason="fast mode"
    model_cfg=st["models"].get(tier,st["models"]["balanced"])
    return {"tier":tier,"provider":model_cfg.get("provider"),"model":model_cfg.get("model"),"reason":reason,"mode":mode}

def stats():
    return STORE.learning_stats()
