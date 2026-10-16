import os
import statistics
import tempfile
import time
from typing import Dict, Any


def qc_rig_profile(
    frames: int = 48,
    top_n: int = 15,
    target_fps: float = 24.0,
) -> Dict[str, Any]:
    """Profile rig performance in the current Maya scene: why does it play slowly?
    Plays the scene with cached playback off and measures real fps (viewport) and
    evaluation-only fps, then records Maya's profiler over one pass and reports where
    evaluation time goes: by node type, by asset (reference namespace) and the top nodes.
    Also returns scene facts that explain the numbers: evaluation mode, GPU override,
    dynamics (nucleus/hairSystem/nCloth/nRigid settings and the control attribute that
    switches each solver on), deforming meshes whose output feeds other nodes (forces a
    GPU-to-CPU copy every frame), constraints, expressions, blendShapes, skinCluster
    influences, smooth mesh preview and references.
    success is True when the measured fps meets target_fps.
    The scene's playback settings, cached playback and current frame are restored afterwards;
    no scene nodes are modified, and a scene with no unsaved changes before is left with none. Keeps itself under ~55 s by dropping optional passes."""
    import maya.cmds as cmds

    budget_s = 52.0
    t_start = time.perf_counter()

    def elapsed():
        return time.perf_counter() - t_start

    def strip_ns(name):
        return name.rsplit(":", 1)[-1]

    def ns_of(name):
        short = name.rsplit("|", 1)[-1]  # the profiler sometimes reports full DAG paths
        return short.rsplit(":", 1)[0] if ":" in short else ""

    # ---------- timing ----------
    scene_start = int(cmds.playbackOptions(q=True, min=True))
    scene_end = int(cmds.playbackOptions(q=True, max=True))
    end = min(scene_end, scene_start + max(2, frames) - 1)
    n = end - scene_start + 1

    was_modified = cmds.file(q=True, modified=True)
    saved = {
        "time": cmds.currentTime(q=True),
        "pb": {k: cmds.playbackOptions(q=True, **{k: True})
               for k in ("playbackSpeed", "maxPlaybackSpeed", "loop", "by", "min", "max")},
        "cache": cmds.evaluator(name="cache", q=True, enable=True),
    }

    def play_once():
        cmds.currentTime(scene_start)
        t0 = time.perf_counter()
        cmds.play(forward=True, wait=True)
        return n / (time.perf_counter() - t0)

    viewport_runs = []
    eval_only_fps = None
    profile = None
    notes = []
    prof_path = os.path.join(tempfile.gettempdir(), "qc_rig_profile_%d.txt" % os.getpid())
    try:
        cmds.evaluator(name="cache", enable=False)
        cmds.playbackOptions(playbackSpeed=0, maxPlaybackSpeed=0, loop="once", by=1,
                             min=scene_start, max=end)

        warm = play_once()  # rebuilds the evaluation graph; not reported as a measurement
        pass_s = n / max(warm, 0.1)

        viewport_runs.append(play_once())
        if elapsed() + pass_s * 3.5 < budget_s:
            viewport_runs.append(play_once())

        if elapsed() + pass_s * 2.5 < budget_s:
            cmds.currentTime(scene_start)
            cmds.refresh(suspend=True)
            try:
                t0 = time.perf_counter()
                for f in range(scene_start, end + 1):
                    cmds.currentTime(f, update=True)
                eval_only_fps = round(n / (time.perf_counter() - t0), 1)
            finally:
                cmds.refresh(suspend=False)
        else:
            notes.append("evaluation-only pass skipped to stay under the time limit")

        if elapsed() + pass_s * 1.3 + 6 < budget_s:
            cmds.profiler(reset=True)
            cmds.profiler(bufferSize=250)
            cmds.currentTime(scene_start)
            cmds.profiler(sampling=True)
            t0 = time.perf_counter()
            cmds.play(forward=True, wait=True)
            prof_wall = time.perf_counter() - t0
            cmds.profiler(sampling=False)
            cmds.profiler(output=prof_path)
            profile = {"wall_s": prof_wall}
        else:
            notes.append("profiler pass skipped to stay under the time limit; scene too slow for the frame count, lower frames")
    finally:
        cmds.playbackOptions(**saved["pb"])
        cmds.evaluator(name="cache", enable=saved["cache"])
        cmds.currentTime(saved["time"])
        # Everything changed above is restored, so a scene that was clean is clean again;
        # otherwise the next open would ask about unsaved changes that are only playback
        # settings. A scene with real unsaved work keeps its flag.
        if not was_modified:
            cmds.file(modified=False)

    viewport_fps = round(statistics.median(viewport_runs), 1)

    # ---------- profiler file: time per evaluated node ----------
    if profile is not None:
        tab = chr(9)
        names = {}
        per_node = {}
        eval_tok = None
        with open(prof_path, "r", encoding="latin-1") as fh:
            for line in fh:
                if line[:1] == "@":
                    key, _, val = line.partition(" = ")
                    val = val.rstrip()
                    names[key] = val
                    if val == "EvaluateNode":
                        eval_tok = key
                    continue
                if eval_tok is None:
                    continue
                parts = line.split(tab, 5)
                if len(parts) > 5 and parts[1] == eval_tok:
                    node = names.get(parts[2], parts[2])
                    per_node[node] = per_node.get(node, 0) + int(parts[4])
        try:
            os.remove(prof_path)
        except OSError:
            pass

        total_us = sum(per_node.values()) or 1
        by_type, by_ns, node_type = {}, {}, {}
        for node, us in per_node.items():
            t = cmds.nodeType(node) if cmds.objExists(node) else "unknown"
            node_type[node] = t
            by_type[t] = by_type.get(t, 0) + us
            ns = ns_of(node) or "(no namespace)"
            by_ns[ns] = by_ns.get(ns, 0) + us

        def row(us):
            return {"ms_per_frame": round(us / 1000.0 / n, 2), "pct": round(100.0 * us / total_us, 1)}

        profile.update({
            "frames": n,
            "fps_while_profiling": round(n / profile.pop("wall_s"), 1),
            "evaluation_cpu_ms_per_frame": round(total_us / 1000.0 / n, 1),
            "note": "CPU time summed over all evaluation threads; % is share of evaluation work",
            "by_node_type": [dict(type=t, **row(us)) for t, us in
                             sorted(by_type.items(), key=lambda kv: -kv[1])[:12]],
            "by_asset_namespace": [dict(namespace=k, **row(us)) for k, us in
                                   sorted(by_ns.items(), key=lambda kv: -kv[1])[:10]],
            "top_nodes": [dict(node=k, type=node_type[k], **row(us)) for k, us in
                          sorted(per_node.items(), key=lambda kv: -kv[1])[:top_n]],
        })

    # ---------- scene facts ----------
    facts = {
        "evaluation_mode": cmds.evaluationManager(q=True, mode=True)[0],
        "gpu_override_enabled": bool(cmds.evaluator(name="deformer", q=True, enable=True)),
        "cached_playback_enabled": bool(saved["cache"]),
        "expressions": len(cmds.ls(type="expression") or []),
    }

    con_counts = {}
    for c in cmds.ls(type="constraint") or []:
        t = cmds.nodeType(c)
        con_counts[t] = con_counts.get(t, 0) + 1
    facts["constraints"] = con_counts

    # dynamics: solvers, their settings, and what switches them on
    dyn = []
    for nu in cmds.ls(type="nucleus") or []:
        enable_src = cmds.listConnections(nu + ".enable", s=True, d=False, plugs=True,
                                          skipConversionNodes=True) or []
        dyn.append({
            "nucleus": nu,
            "enabled": bool(cmds.getAttr(nu + ".enable")),
            "enable_driven_by": enable_src[0] if enable_src else None,
            "subSteps": cmds.getAttr(nu + ".subSteps"),
            "maxCollisionIterations": cmds.getAttr(nu + ".maxCollisionIterations"),
            "start_frame": cmds.getAttr(nu + ".startFrame"),
        })
    facts["nucleus_solvers"] = dyn[:12]
    facts["hair_systems"] = [{
        "node": h, "iterations": cmds.getAttr(h + ".iterations"),
        "collide": bool(cmds.getAttr(h + ".collide")),
        "selfCollide": bool(cmds.getAttr(h + ".selfCollide")),
    } for h in (cmds.ls(type="hairSystem") or [])][:12]
    colliders = []
    for t in ("nRigid", "nCloth"):
        for nd in cmds.ls(type=t) or []:
            src = cmds.listConnections(nd + ".inputMesh", s=True, d=False, shapes=True) or []
            colliders.append({"node": nd, "type": t, "input_mesh": src[0] if src else None,
                              "frozen": bool(cmds.getAttr(nd + ".frozen"))})
    facts["nucleus_objects"] = colliders[:16]

    # deforming meshes: deformer stack, and any non-display consumers of the deformed output
    deform_types = {"skinCluster", "blendShape", "cluster", "lattice", "wrap", "deltaMush",
                    "tension", "nonLinear", "wire", "proximityWrap", "ffd", "morph", "softMod"}
    deforming, out_consumers, smooth_on = [], [], []
    for shape in cmds.ls(type="mesh", noIntermediate=True) or []:
        hist = cmds.listHistory(shape, pruneDagObjects=True) or []
        stack = [h for h in hist if cmds.nodeType(h) in deform_types]
        if cmds.getAttr(shape + ".displaySmoothMesh"):
            smooth_on.append(shape)
        if not stack:
            continue
        deforming.append({"mesh": shape, "verts": cmds.polyEvaluate(shape, vertex=True),
                          "deformers": [cmds.nodeType(h) for h in stack]})
        for plug in ("worldMesh", "outMesh"):
            for c in cmds.listConnections(shape + "." + plug, s=False, d=True, shapes=True) or []:
                if cmds.nodeType(c) not in ("groupParts", "groupId", "objectSet", "shadingEngine"):
                    out_consumers.append({"mesh": shape, "output": plug, "consumer": c,
                                          "consumer_type": cmds.nodeType(c)})
    facts["deforming_meshes"] = {"count": len(deforming), "examples": deforming[:8]}
    facts["deformed_output_consumers"] = {
        "count": len(out_consumers), "items": out_consumers[:12],
        "why_it_matters": "with GPU override on, a deforming mesh whose output feeds another node is copied back from the GPU every frame",
    }
    facts["smooth_mesh_preview"] = {"count": len(smooth_on), "examples": smooth_on[:8]}

    bs = []
    for b in cmds.ls(type="blendShape") or []:
        bs.append({"node": b, "targets": len(cmds.getAttr(b + ".weight", multiIndices=True) or [])})
    facts["blendshapes"] = bs[:10]
    sk = []
    for s in cmds.ls(type="skinCluster") or []:
        geo = cmds.skinCluster(s, q=True, geometry=True) or [""]
        sk.append({"node": s, "mesh": geo[0],
                   "influences": len(cmds.skinCluster(s, q=True, influence=True) or []),
                   "max_influences": cmds.getAttr(s + ".maxInfluences"),
                   "max_enforced": bool(cmds.getAttr(s + ".maintainMaxInfluences"))})
    sk.sort(key=lambda d: -d["influences"])
    facts["skin_clusters"] = {"count": len(sk), "largest": sk[:6]}

    refs = []
    for rf in cmds.file(q=True, reference=True) or []:
        ns = cmds.referenceQuery(rf, namespace=True).lstrip(":")
        refs.append({"namespace": ns,
                     "file": cmds.referenceQuery(rf, filename=True, withoutCopyNumber=True),
                     "loaded": cmds.referenceQuery(rf, isLoaded=True)})
    facts["references"] = refs[:20]

    result = {
        "success": viewport_fps >= target_fps,
        "scene": cmds.file(q=True, sceneName=True),
        "target_fps": target_fps,
        "viewport_fps": viewport_fps,
        "viewport_fps_runs": [round(v, 1) for v in viewport_runs],
        "evaluation_only_fps": eval_only_fps,
        "frames_measured": n,
        "frame_range": [scene_start, end],
        "profile": profile,
        "scene_facts": facts,
        "notes": notes,
        "tool_seconds": round(elapsed(), 1),
    }
    return result
