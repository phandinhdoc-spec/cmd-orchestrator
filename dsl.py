from __future__ import annotations
import json

def _q(v):
    return json.dumps("" if v is None else str(v), ensure_ascii=False)

def _triple(v):
    s = "" if v is None else str(v)
    return '"""' + s.replace('"""', '\\"\\"\\"') + '"""'

def render_prompt_review(prompt):
    if not prompt:
        return "prompt_review { status = \"MISSING\" }"
    return "\n".join([
        "prompt_review {",
        f"  status    = {_q(prompt.get('status') or 'PENDING')}",
        f"  selection = {_q(prompt.get('selection') or '')}",
        "",
        "  original = " + _triple(prompt.get("original_prompt") or ""),
        "",
        "  grilled  = " + _triple(prompt.get("grilled_prompt") or ""),
        "",
        "  selected = " + _triple(prompt.get("selected_prompt") or ""),
        "}",
    ])

def render_plan(tree, run=None):
    lines = []
    rid = (run or {}).get("run_id", "")
    lines.append(f"plan {_q(rid)} {{")
    if run:
        lines.append(f"  state = {_q(run.get('status') or '')}")
        lines.append(f"  stage = {_q(run.get('current_stage') or '')}")
        lines.append(f"  review = {_q(run.get('review_state') or '')}")
    for task in tree or []:
        lines.append("")
        lines.append(f"  task {task['task_id']} {_q(task.get('title') or '')} {{")
        if task.get("description"):
            lines.append(f"    description = {_triple(task['description'])}")
        deps = task.get("dependencies") or []
        lines.append(f"    depends = {json.dumps(deps, ensure_ascii=False)}")
        lines.append(f"    status = {_q(task.get('status') or 'PENDING')}")
        for unit in task.get("work_units") or []:
            lines.append("")
            lines.append(f"    work_unit {unit['unit_id']} {_q(unit.get('title') or '')} {{")
            if unit.get("description"):
                lines.append(f"      description = {_triple(unit['description'])}")
            lines.append(f"      depends = {json.dumps(unit.get('dependencies') or [], ensure_ascii=False)}")
            route = f"{unit.get('provider') or '-'}/{unit.get('model') or '-'}"
            lines.append(f"      route = {_q(route)}")
            lines.append(f"      route_source = {_q(unit.get('route_source') or 'hermes')}")
            if unit.get("reasoning"):
                lines.append(f"      why = {_triple(unit['reasoning'])}")
            lines.append(f"      risk = {_q(unit.get('risk') or 'medium')}")
            lines.append(f"      status = {_q(unit.get('status') or 'PENDING')}")
            if unit.get("verification"):
                lines.append(f"      verify = {_triple(unit['verification'])}")
            for step in unit.get("steps") or []:
                lines.append(
                    f"      step {step['step_id']} {_q(step.get('title') or '')} "
                    f"{{ status = {_q(step.get('status') or 'PENDING')} }}"
                )
            lines.append("    }")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines)

def render_learning(rows):
    if not rows:
        return "learning_store { /* empty */ }"
    lines = ["learning_store {"]
    for row in rows:
        lid = row.get("learning_id") or row.get("id") or "?"
        lines += [
            "",
            f"  learning {lid} {{",
            f"    kind = {_q(row.get('kind') or 'observation')}",
            f"    source = {_q(row.get('source') or '')}",
            f"    status = {_q(row.get('status') or '')}",
            f"    scope = {_q(row.get('scope') or 'general')}",
            f"    confidence = {_q(row.get('confidence') or '')}",
            f"    priority = {int(row.get('priority') or 0)}",
            f"    statement = {_triple(row.get('statement') or '')}",
        ]
        if row.get("evidence"):
            lines.append(f"    evidence = {_triple(row['evidence'])}")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines)
