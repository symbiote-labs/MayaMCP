from typing import Dict, Any, Optional

def qc_scene_info(
    expected_start_frame: Optional[int] = None,
    expected_end_frame: Optional[int] = None,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> Dict[str, Any]:
    """Inspect the currently open Maya scene and return QC-relevant metadata.
    Checks frame range, render settings, cameras, lights, references, and audio.
    Optionally compares against expected values and reports mismatches.
    Must call qc_open_scene first to load the scene."""
    import maya.cmds as cmds

    # Frame range
    start = int(cmds.playbackOptions(q=True, minTime=True))
    end = int(cmds.playbackOptions(q=True, maxTime=True))
    frame_count = end - start + 1

    # Render settings
    width = cmds.getAttr("defaultResolution.width")
    height = cmds.getAttr("defaultResolution.height")
    pixel_aspect = cmds.getAttr("defaultResolution.deviceAspectRatio")

    # Cameras — find transform names
    all_cameras = cmds.ls(type="camera", long=True) or []
    camera_transforms = []
    for cam in all_cameras:
        parent = cmds.listRelatives(cam, parent=True, fullPath=True)
        if parent:
            camera_transforms.append(parent[0].split("|")[-1])
    has_shot_cam = "shotCam" in camera_transforms

    # Lights — check all common types including Arnold
    light_types = ["directionalLight", "pointLight", "spotLight", "areaLight",
                   "aiAreaLight", "aiSkyDomeLight", "aiPhotometricLight"]
    lights = []
    for lt in light_types:
        found = cmds.ls(type=lt) or []
        lights.extend(found)

    # References
    refs = cmds.file(q=True, reference=True) or []
    ref_info = []
    for ref in refs:
        try:
            ns = cmds.file(ref, q=True, namespace=True)
            loaded = cmds.file(ref, q=True, deferReference=True) is False
            ref_info.append({"path": ref, "namespace": ns, "loaded": loaded})
        except RuntimeError:
            ref_info.append({"path": ref, "namespace": "unknown", "loaded": False})

    # Audio
    audio_nodes = cmds.ls(type="audio") or []

    # Mismatches against expected values
    mismatches = []
    if expected_start_frame is not None and start != expected_start_frame:
        mismatches.append(f"Start frame: expected {expected_start_frame}, got {start}")
    if expected_end_frame is not None and end != expected_end_frame:
        mismatches.append(f"End frame: expected {expected_end_frame}, got {end}")
    if expected_width is not None and width != expected_width:
        mismatches.append(f"Width: expected {expected_width}, got {width}")
    if expected_height is not None and height != expected_height:
        mismatches.append(f"Height: expected {expected_height}, got {height}")

    return {
        "success": True,
        "frame_range": {"start": start, "end": end, "count": frame_count},
        "render_settings": {"width": width, "height": height, "pixel_aspect": pixel_aspect},
        "cameras": {"names": camera_transforms, "count": len(camera_transforms), "has_shot_cam": has_shot_cam},
        "lights": {"names": lights, "count": len(lights)},
        "references": {"items": ref_info, "count": len(ref_info)},
        "audio": {"nodes": audio_nodes, "count": len(audio_nodes)},
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
    }
