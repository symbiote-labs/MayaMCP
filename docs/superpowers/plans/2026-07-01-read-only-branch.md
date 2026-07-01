# Read-Only MayaMCP Branch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `read-only` git branch of MayaMCP that exposes only non-destructive tools by deleting the 12 mutating tool files.

**Architecture:** The MCP server auto-discovers tools by walking `mayatools/`. Deleting a file removes that tool from the API. No server code changes are needed — the branch is the isolation mechanism.

**Tech Stack:** Python, git

## Global Constraints

- Branch from current `main` HEAD — do not cherry-pick or rebase
- No changes to `src/maya_mcp_server.py` or any retained tool file
- Exactly 10 tool `.py` files must remain under `src/mayatools/` after deletion (plus `PLACE-YOUR-SCRIPTS-HERE` placeholder)

---

### Task 1: Create the `read-only` branch and delete mutating tools

**Files:**
- Delete: `src/mayatools/object/create_object.py`
- Delete: `src/mayatools/object/create_advanced_model.py`
- Delete: `src/mayatools/object/create_curve.py`
- Delete: `src/mayatools/material/create_material.py`
- Delete: `src/mayatools/object/curve_modeling.py`
- Delete: `src/mayatools/object/mesh_operations.py`
- Delete: `src/mayatools/object/organize_objects.py`
- Delete: `src/mayatools/object/set_object_attribute.py`
- Delete: `src/mayatools/object/set_object_transform_attributes.py`
- Delete: `src/mayatools/scene/generate_scene.py`
- Delete: `src/mayatools/scene/scene_new.py`
- Delete: `src/mayatools/scene/scene_save.py`

**Interfaces:**
- Produces: a `read-only` branch where `OperationsManager.find_tools()` discovers exactly 10 tools

- [ ] **Step 1: Create the branch**

```bash
git checkout -b read-only
```

Expected output:
```
Switched to a new branch 'read-only'
```

- [ ] **Step 2: Delete the 12 mutating tool files**

```bash
git rm \
  src/mayatools/object/create_object.py \
  src/mayatools/object/create_advanced_model.py \
  src/mayatools/object/create_curve.py \
  src/mayatools/material/create_material.py \
  src/mayatools/object/curve_modeling.py \
  src/mayatools/object/mesh_operations.py \
  src/mayatools/object/organize_objects.py \
  src/mayatools/object/set_object_attribute.py \
  src/mayatools/object/set_object_transform_attributes.py \
  src/mayatools/scene/generate_scene.py \
  src/mayatools/scene/scene_new.py \
  src/mayatools/scene/scene_save.py
```

Expected output — 12 lines of:
```
rm 'src/mayatools/object/create_object.py'
rm 'src/mayatools/object/create_advanced_model.py'
...
rm 'src/mayatools/scene/scene_save.py'
```

- [ ] **Step 3: Verify exactly 10 tool files remain**

```bash
find src/mayatools -name "*.py" | sort
```

Expected output (exactly these 10 files):
```
src/mayatools/object/get_object_attributes.py
src/mayatools/object/list_objects_by_type.py
src/mayatools/scene/clear_selection_list.py
src/mayatools/scene/scene_open.py
src/mayatools/scene/select_object.py
src/mayatools/scene/viewport_focus.py
src/mayatools/thirdparty/qc_asset_check.py
src/mayatools/thirdparty/qc_check_render.py
src/mayatools/thirdparty/qc_open_scene.py
src/mayatools/thirdparty/qc_playback_test.py
src/mayatools/thirdparty/qc_scene_info.py
```

If any extra `.py` file appears, it is a mutating tool that was missed — remove it. If any of the 10 expected files is missing, the wrong file was deleted.

- [ ] **Step 4: Verify git status shows only deletions**

```bash
git status
```

Expected: 12 deleted files staged, no other changes.

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: read-only mode — remove all mutating tools

Removes 12 tools that create, modify, or delete scene content or write
to the user's project files. Retained tools cover inspection, QC
workflows, and transient UI state (selection, viewport).

Removed: create_object, create_advanced_model, create_curve,
create_material, curve_modeling, mesh_operations, organize_objects,
set_object_attribute, set_object_transform_attributes, generate_scene,
scene_new, scene_save

Retained: get_object_attributes, list_objects_by_type, scene_open,
select_object, clear_selection_list, viewport_focus, qc_open_scene,
qc_scene_info, qc_asset_check, qc_playback_test, qc_check_render
EOF
)"
```

- [ ] **Step 6: Confirm the branch diverges from main by exactly those deletions**

```bash
git diff main...read-only --name-status
```

Expected: 12 lines, all starting with `D` (deleted). If any `M` (modified) or `A` (added) lines appear, something unintended changed.
