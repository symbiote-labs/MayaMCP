import os
from typing import Dict, Any, List, Optional

def qc_asset_check(
    expected_assets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check all referenced assets in the current Maya scene. For each reference,
    reports: namespace, file path, whether it's positioned (not at origin),
    keyframe info including tangent type (stepped vs spline), and temp_ prefix.
    Optionally checks that expected assets (by namespace or filename substring) are present.
    Assets not in expected_assets and lacking 'temp_' prefix are flagged as unknown.
    Must call qc_open_scene first to load the scene."""
    import maya.cmds as cmds

    refs = cmds.file(q=True, reference=True) or []
    asset_results = []

    scene_start = int(cmds.playbackOptions(q=True, minTime=True))
    scene_end = int(cmds.playbackOptions(q=True, maxTime=True))
    scene_mid = scene_start + (scene_end - scene_start) // 2

    for ref_path in refs:
        try:
            ns = cmds.file(ref_path, q=True, namespace=True)
        except RuntimeError:
            asset_results.append({
                "path": ref_path, "namespace": "error", "status": "error",
                "message": "Could not query namespace",
            })
            continue

        # Check positioning on the root group node (first top-level transform)
        ns_top_nodes = cmds.ls(f"{ns}:*", type="transform", long=False) or []
        # Filter to true top-level nodes (no parent in same namespace)
        root_nodes = []
        for node in ns_top_nodes:
            parent = cmds.listRelatives(node, parent=True)
            if not parent or not parent[0].startswith(f"{ns}:"):
                root_nodes.append(node)

        at_origin = True
        for node in root_nodes:
            try:
                tx = cmds.getAttr(f"{node}.translateX")
                ty = cmds.getAttr(f"{node}.translateY")
                tz = cmds.getAttr(f"{node}.translateZ")
                if abs(tx) > 0.001 or abs(ty) > 0.001 or abs(tz) > 0.001:
                    at_origin = False
                    break
            except (RuntimeError, ValueError):
                continue

        # Check for animation keyframes — query entire namespace at once
        all_ns_nodes = cmds.ls(f"{ns}:*", long=True) or []
        keyframe_count = 0
        keyed_nodes = 0
        first_key = None
        last_key = None
        has_stepped_keys = False
        has_mid_frame_key = False

        for node in all_ns_nodes:
            try:
                keys = cmds.keyframe(node, q=True, timeChange=True) or []
                if not keys:
                    continue
                keyed_nodes += 1
                keyframe_count += len(keys)
                node_first = min(keys)
                node_last = max(keys)
                if first_key is None or node_first < first_key:
                    first_key = node_first
                if last_key is None or node_last > last_key:
                    last_key = node_last
                # Check for mid-frame key
                if any(abs(k - scene_mid) <= 1.0 for k in keys):
                    has_mid_frame_key = True
                # Check tangent type (stepped = blocked animation)
                tangents = cmds.keyTangent(node, q=True, outTangentType=True) or []
                if any(t == "step" for t in tangents):
                    has_stepped_keys = True
            except (RuntimeError, ValueError):
                continue

        has_first_key = first_key is not None and abs(first_key - scene_start) <= 1.0
        has_last_key = last_key is not None and abs(last_key - scene_end) <= 1.0

        # Check temp_ prefix
        basename = os.path.basename(ref_path)
        is_temp = basename.startswith("temp_")

        # Flag unknown assets (not in expected list and no temp_ prefix)
        is_known = True
        if expected_assets:
            is_known = any(
                exp.lower() in ns.lower() or exp.lower() in basename.lower()
                for exp in expected_assets
            )
        is_unknown_unlabeled = not is_known and not is_temp

        asset_results.append({
            "path": ref_path,
            "namespace": ns,
            "basename": basename,
            "is_temp": is_temp,
            "is_unknown_unlabeled": is_unknown_unlabeled,
            "positioned": not at_origin,
            "at_origin_warning": at_origin,
            "animation": {
                "has_keys": keyframe_count > 0,
                "keyframe_count": keyframe_count,
                "keyed_nodes": keyed_nodes,
                "first_key": first_key,
                "last_key": last_key,
                "has_first_frame_key": has_first_key,
                "has_mid_frame_key": has_mid_frame_key,
                "has_last_frame_key": has_last_key,
                "has_stepped_keys": has_stepped_keys,
            },
            "root_nodes": len(root_nodes),
        })

    # Check expected assets are present
    found_namespaces = [a["namespace"] for a in asset_results]
    found_basenames = [a.get("basename", "") for a in asset_results]
    missing_assets = []
    if expected_assets:
        for expected in expected_assets:
            matched = any(
                expected.lower() in ns.lower() or expected.lower() in bn.lower()
                for ns, bn in zip(found_namespaces, found_basenames)
            )
            if not matched:
                missing_assets.append(expected)

    # success reflects whether the check PASSED, not just "tool didn't crash"
    has_issues = (
        len(missing_assets) > 0
        or any(a.get("at_origin_warning") for a in asset_results)
        or any(a.get("is_unknown_unlabeled") for a in asset_results)
    )

    return {
        "success": not has_issues,
        "assets": asset_results,
        "asset_count": len(asset_results),
        "missing_assets": missing_assets,
        "missing_count": len(missing_assets),
    }
