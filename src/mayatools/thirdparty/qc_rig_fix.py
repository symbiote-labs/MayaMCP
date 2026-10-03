import os
from typing import Dict, Any, List, Optional


def qc_rig_fix(
    fix: str = "dynamics_off",
    namespaces: Optional[List[str]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Apply a safe, shot-level rig performance fix in the current Maya scene. Only call with
    dry_run=False after the user approved the exact changes shown by a dry run.
    fix="dynamics_off": switch off nucleus simulations (e.g. a tail or cape sim left on in an
    animation rig) using the rig's own switch, the control attribute wired to each nucleus
    .enable; dynamic/FK blend attributes on that same control (name contains "dyn") are set
    to their minimum so the part falls back to its FK/animated pose. Nucleus nodes with no
    switch are set to enable=0 directly.
    namespaces: limit to these reference namespaces (e.g. ["Tiger_01"]); empty = all.
    dry_run=True (default) changes nothing and returns the planned changes.
    dry_run=False first saves the scene as <name>_qcfix.ma next to the original (the original
    file is never overwritten), applies the changes in one undo chunk and saves the _qcfix
    file. Only changes values on the scene's own or referenced nodes; never edits rig files.
    Re-run qc_rig_profile afterwards to measure the effect.
    success is True when every planned change was applied (or, for a dry run, when there is
    something to change)."""
    import maya.cmds as cmds

    if fix != "dynamics_off":
        return {"success": False, "message": "Unknown fix '%s'. Supported: dynamics_off" % fix}

    wanted = [n.strip(":") for n in (namespaces or []) if n]

    def in_scope(node):
        short = node.rsplit("|", 1)[-1]
        ns = short.rsplit(":", 1)[0] if ":" in short else ""
        return not wanted or ns in wanted

    # ---------- plan ----------
    plan = []  # dicts: plug, before, after, reason
    seen = set()

    def add(plug, after, reason):
        if plug in seen:
            return
        seen.add(plug)
        before = cmds.getAttr(plug)
        if before == after or (isinstance(before, bool) and int(before) == after):
            return
        plan.append({"plug": plug, "before": before, "after": after, "reason": reason})

    solvers = [nu for nu in (cmds.ls(type="nucleus") or []) if in_scope(nu)]
    skipped = []
    for nu in solvers:
        src = cmds.listConnections(nu + ".enable", s=True, d=False, plugs=True,
                                   skipConversionNodes=True) or []
        if not src:
            add(nu + ".enable", 0, "nucleus has no rig switch; disable it directly")
            continue
        switch = src[0]
        ctrl, attr = switch.split(".", 1)
        if cmds.listConnections(switch, s=True, d=False):
            skipped.append({"nucleus": nu, "switch": switch,
                            "reason": "the switch is itself driven (animated or connected); not touched"})
            continue
        add(switch, 0, "rig switch that enables %s" % nu)
        for a in cmds.listAttr(ctrl, keyable=True, unlocked=True) or []:
            if a == attr or "dyn" not in a.lower():
                continue
            if cmds.getAttr(ctrl + "." + a, type=True) not in ("double", "float", "long", "short", "bool", "doubleLinear", "doubleAngle"):
                continue
            if cmds.listConnections(ctrl + "." + a, s=True, d=False):
                continue
            lo = cmds.attributeQuery(a, node=ctrl, minimum=True)[0] if cmds.attributeQuery(a, node=ctrl, minExists=True) else 0
            add(ctrl + "." + a, lo, "dynamic/FK blend on the same control; back to the non-dynamic pose")

    scene = cmds.file(q=True, sceneName=True)
    result = {
        "fix": fix,
        "dry_run": dry_run,
        "scene": scene,
        "solvers_in_scope": solvers,
        "planned_changes": plan,
        "skipped": skipped,
    }
    if dry_run:
        result["success"] = len(plan) > 0
        result["message"] = ("%d change(s) planned; nothing changed. Show them to the user and call again "
                             "with dry_run=False after approval." % len(plan)) if plan else "Nothing to change."
        return result
    if not plan:
        result["success"] = False
        result["message"] = "Nothing to change; scene not saved."
        return result
    if not scene:
        result["success"] = False
        result["message"] = "The scene has never been saved; save it first so a _qcfix copy can be made."
        return result

    # ---------- apply: save as _qcfix first, then change ----------
    root, ext = os.path.splitext(scene)
    qcfix_path = scene if root.endswith("_qcfix") else root + "_qcfix" + (ext or ".ma")
    file_type = "mayaBinary" if ext.lower() == ".mb" else "mayaAscii"
    cmds.file(rename=qcfix_path)
    cmds.file(save=True, type=file_type, force=True)

    applied, failed = [], []
    cmds.undoInfo(openChunk=True, chunkName="qc_rig_fix")
    try:
        for ch in plan:
            try:
                cmds.setAttr(ch["plug"], ch["after"])
                applied.append(ch["plug"])
            except RuntimeError as e:
                failed.append({"plug": ch["plug"], "error": str(e)})
    finally:
        cmds.undoInfo(closeChunk=True)
    cmds.file(save=True, type=file_type, force=True)

    result.update({
        "success": not failed,
        "applied": applied,
        "failed": failed,
        "original_file": scene,
        "saved_as": qcfix_path,
        "message": ("Applied %d change(s) and saved %s. The original %s is untouched; "
                    "one undo (Ctrl+Z) reverts the changes in this session."
                    % (len(applied), os.path.basename(qcfix_path), os.path.basename(scene))),
    })
    return result
