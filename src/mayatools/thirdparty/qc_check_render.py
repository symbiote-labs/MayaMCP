import os
import time
import uuid
from typing import Dict, Any, List, Optional

def qc_check_render(
    output_dir: Optional[str] = None,
    frames: Optional[List[int]] = None,
    width: int = 1024,
    height: int = 576,
    camera: str = "shotCam",
) -> Dict[str, Any]:
    """Render check frames from the specified camera (default: shotCam).
    If frames is not provided, renders first, middle, and last frame.
    Uses Viewport 2.0 hardware render (ogsRender) for lighting-accurate output,
    falling back to playblast if ogsRender is unavailable.
    Returns paths to rendered images and timing info.
    Must call qc_open_scene first to load the scene."""
    import maya.cmds as cmds

    # Generate unique output dir to prevent concurrent QC runs from clobbering
    if output_dir is None:
        run_id = uuid.uuid4().hex[:8]
        output_dir = f"/tmp/qc_renders/{run_id}"

    # Verify camera exists — use short names (split on "|") to match
    # qc_scene_info's convention. Long paths like "|shotCam" won't match "shotCam".
    all_cameras = cmds.ls(type="camera", long=True) or []
    camera_transforms = []
    for cam in all_cameras:
        parent = cmds.listRelatives(cam, parent=True, fullPath=True)
        if parent:
            camera_transforms.append(parent[0].split("|")[-1])

    if camera not in camera_transforms:
        return {
            "success": False,
            "message": f"Camera '{camera}' not found. Available: {camera_transforms}",
        }

    # Determine frames to render
    start = int(cmds.playbackOptions(q=True, minTime=True))
    end = int(cmds.playbackOptions(q=True, maxTime=True))
    if frames is None:
        mid = start + (end - start) // 2
        frames = [start, mid, end]

    os.makedirs(output_dir, exist_ok=True)

    rendered_files = []
    total_time = 0
    render_method = "unknown"

    for frame in frames:
        cmds.currentTime(frame, edit=True)
        output_path = os.path.join(output_dir, f"qc_frame_{int(frame):04d}.png")

        t0 = time.time()
        try:
            # Try ogsRender first (Viewport 2.0 hardware render)
            try:
                cmds.ogsRender(
                    camera=camera,
                    width=width,
                    height=height,
                    enableMultisample=False,
                )
                # ogsRender writes to render view; save from there
                cmds.renderWindowEditor("renderView", e=True, writeImage=output_path)
                render_method = "ogsRender"
            except (RuntimeError, AttributeError):
                # Fallback to playblast
                base_path = os.path.join(output_dir, f"qc_frame_{int(frame):04d}")
                cmds.playblast(
                    frame=[frame],
                    format="image",
                    compression="png",
                    quality=100,
                    width=width,
                    height=height,
                    filename=base_path,
                    sequenceTime=False,
                    clearCache=True,
                    viewer=False,
                    showOrnaments=False,
                    offScreen=True,
                    camera=camera,
                )
                # playblast appends frame number
                pb_path = f"{base_path}.{int(frame):04d}.png"
                if os.path.exists(pb_path):
                    os.rename(pb_path, output_path)
                render_method = "playblast"

            elapsed = time.time() - t0
            total_time += elapsed

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                # A 1024x576 black PNG is typically 2-5KB; real content is 50KB+
                is_black = file_size < 10240
                rendered_files.append({
                    "frame": int(frame),
                    "path": output_path,
                    "size_bytes": file_size,
                    "render_seconds": round(elapsed, 2),
                    "possibly_black": is_black,
                    "method": render_method,
                })
            else:
                rendered_files.append({
                    "frame": int(frame),
                    "path": None,
                    "error": "Output file not found after render",
                    "render_seconds": round(elapsed, 2),
                })
        except Exception as e:
            rendered_files.append({
                "frame": int(frame),
                "path": None,
                "error": str(e),
                "render_seconds": round(time.time() - t0, 2),
            })

    successful = [f for f in rendered_files if f.get("path")]
    black_frames = [f for f in rendered_files if f.get("possibly_black")]

    return {
        "success": len(successful) == len(frames),
        "rendered_files": rendered_files,
        "total_frames": len(frames),
        "successful_frames": len(successful),
        "black_frame_warnings": len(black_frames),
        "total_render_seconds": round(total_time, 2),
        "output_dir": output_dir,
        "render_method": render_method,
    }
