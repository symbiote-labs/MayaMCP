# Read-Only MayaMCP Branch — Design Spec

**Date:** 2026-07-01  
**Branch:** `read-only`  
**Status:** Approved

## Goal

Produce a variant of the MayaMCP server that exposes only non-destructive tools — tools that cannot modify, create, or delete content on the user's machine or in their Maya scene. The primary use case is safe inspection and QC workflows where an LLM assistant should never accidentally alter user work.

## Mechanism

MayaMCP's `OperationsManager.find_tools()` auto-discovers tools by walking the `mayatools/` directory. Removing a tool's `.py` file removes it from the MCP server's exposed API. No changes to `maya_mcp_server.py` are required.

The `read-only` branch is branched from `main`. The only difference from `main` is the deletion of 12 mutating tool files.

## Tools Removed (12 files deleted)

| File | Reason for removal |
|---|---|
| `object/create_object.py` | Creates new geometry in the scene |
| `object/create_advanced_model.py` | Creates complex geometry in the scene |
| `object/create_curve.py` | Creates new curve objects |
| `material/create_material.py` | Creates and assigns materials |
| `object/curve_modeling.py` | Creates geometry from curves |
| `object/mesh_operations.py` | Modifies mesh geometry (extrude, bevel, boolean, etc.) |
| `object/organize_objects.py` | Groups, parents, or moves objects |
| `object/set_object_attribute.py` | Mutates object attribute values |
| `object/set_object_transform_attributes.py` | Mutates transform (translate, rotate, scale) |
| `scene/generate_scene.py` | Creates a full scene with many objects |
| `scene/scene_new.py` | Destroys the current scene and creates a blank one |
| `scene/scene_save.py` | Writes the scene to disk |

## Tools Retained (10 tools)

| File | Rationale |
|---|---|
| `object/get_object_attributes.py` | Pure read — queries attribute values |
| `object/list_objects_by_type.py` | Pure read — lists scene contents |
| `scene/scene_open.py` | Loads a scene for inspection (needed for QC workflows) |
| `scene/select_object.py` | UI state change only; no scene data mutated |
| `scene/clear_selection_list.py` | UI state change only; no scene data mutated |
| `scene/viewport_focus.py` | Viewport camera framing only; no data mutation |
| `thirdparty/qc_open_scene.py` | Opens a scene file for QC inspection |
| `thirdparty/qc_scene_info.py` | Pure read — queries scene metadata |
| `thirdparty/qc_asset_check.py` | Pure read — queries referenced asset info |
| `thirdparty/qc_playback_test.py` | Scrubs timeline to measure FPS; no persistent change |
| `thirdparty/qc_check_render.py` | Writes rendered frames to `/tmp` only (not user project) |

## What "Read-Only" Means Here

- **No scene content changes:** Cannot create, delete, or modify objects, materials, or geometry.
- **No file writes to user's project:** `scene_save` is removed. `qc_check_render` only writes to `/tmp`.
- **UI state is allowed:** Selection and viewport changes are transient and do not affect saved data.
- **Scene loading is allowed:** Opening a file for inspection is required for QC workflows. Loading a file replaces the active scene, but the user controls which file is opened.

## Implementation Steps

1. Create `read-only` branch from `main`
2. Delete the 12 mutating tool files listed above
3. Commit with a clear message describing the read-only policy
4. Verify by running `find src/mayatools -name "*.py" | sort` to confirm only the 10 retained tools remain

## Non-Goals

- No runtime flag to toggle read-only mode (handled by branch)
- No changes to the MCP server discovery logic
- No changes to the QC tools' internal behavior
