import time
from typing import Dict, Any

def qc_playback_test(
    sample_frames: int = 30,
) -> Dict[str, Any]:
    """Play through the current scene and measure playback FPS.
    Reports whether the scene can achieve 30fps or better.
    Must call qc_open_scene first to load the scene."""
    import maya.cmds as cmds

    start = int(cmds.playbackOptions(q=True, minTime=True))
    end = int(cmds.playbackOptions(q=True, maxTime=True))
    total_frames = end - start + 1

    test_frames = min(sample_frames, total_frames)
    test_end = start + test_frames - 1

    t0 = time.time()
    for frame in range(start, int(test_end) + 1):
        cmds.currentTime(frame, edit=True)
    elapsed = time.time() - t0

    fps = test_frames / elapsed if elapsed > 0 else 0

    return {
        "success": True,
        "measured_fps": round(fps, 1),
        "meets_30fps": fps >= 30.0,
        "frames_tested": test_frames,
        "total_frames": total_frames,
        "elapsed_seconds": round(elapsed, 2),
    }
