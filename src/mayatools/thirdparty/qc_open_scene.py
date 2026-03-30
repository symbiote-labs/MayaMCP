from typing import Dict, Any

def qc_open_scene(file_path: str) -> Dict[str, Any]:
    """Open a Maya scene file and report integrity. Returns success status,
    any errors or warnings captured during open, and basic scene info.
    Use this as the first step in QC — it validates the file can be loaded.

    Uses OpenMaya.MCommandMessage callback for comprehensive error capture
    in interactive Maya (catches C++ warnings for missing textures, unknown
    nodes, unresolved references). Falls back to exception handling +
    filePathEditor in standalone mode where MCommandMessage is unreliable."""
    import maya.cmds as cmds

    errors = []
    warnings = []
    infos = []
    callback_id = None

    def _capture_message(msg, msg_type, _client_data):
        """MCommandMessage callback — captures all Maya output by type."""
        import maya.OpenMaya as OpenMaya
        msg = msg.strip()
        if not msg:
            return
        if msg_type == OpenMaya.MCommandMessage.kError:
            errors.append(msg)
        elif msg_type == OpenMaya.MCommandMessage.kWarning:
            warnings.append(msg)
        elif msg_type in (OpenMaya.MCommandMessage.kInfo,
                          OpenMaya.MCommandMessage.kDisplay):
            infos.append(msg)

    # Detect whether we're in interactive or standalone mode.
    # MCommandMessage callbacks are only reliable with a GUI context.
    use_callback = False
    try:
        import maya.OpenMaya as OpenMaya
        # If cmds.about(batch=True) is False, we have a GUI context
        use_callback = not cmds.about(batch=True)
    except (ImportError, RuntimeError):
        pass

    if use_callback:
        callback_id = OpenMaya.MCommandMessage.addCommandOutputCallback(
            _capture_message
        )

    try:
        cmds.file(file_path, open=True, force=True)
    except RuntimeError as e:
        errors.append(str(e))
    finally:
        if callback_id is not None:
            OpenMaya.MCommandMessage.removeCallback(callback_id)

    # Standalone fallback: query filePathEditor for unresolved references
    if not use_callback:
        try:
            unresolved = cmds.filePathEditor(query=True, status=True,
                                             listFiles="") or []
            for entry in unresolved:
                if "unresolved" in str(entry).lower():
                    warnings.append(f"Unresolved path: {entry}")
        except RuntimeError:
            pass

    scene_file = cmds.file(q=True, sceneName=True)

    return {
        "success": len(errors) == 0,
        "scene_file": scene_file,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "capture_method": "MCommandMessage" if use_callback else "fallback",
    }
