<!-- .github/copilot-instructions.md for 360_rig_renderer -->
# Copilot / AI assistant quick instructions

Short purpose
- This repository is a small Blender add-on that: (1) exports COLMAP-style rig JSON (rig_config.json) from Blender Collections and (2) batch-renders frames for each visible camera inside each collection.

Big picture (what an agent needs to know)
- Files to read: `rig_json_maker.py` (exports rig JSON), `renderer.py` (batch render operator), `ui.py` (panel exposing properties/operators), and `__init__.py` (register pattern).
- Design choices: each Blender Collection represents a "rig". Visible cameras inside a collection are treated as rig members; the first visible camera in the collection is chosen as the reference sensor.
- Registry pattern: `__init__.py` uses an explicit, static `modules` tuple and calls each module's `register()`/`unregister()` if present. Do NOT use dynamic importlib tricks — follow the static import style.

Key operators & UI
- Export operator: `COLMAP_RIG_OT_export` (bl_idname `colmap_rig.export`) — called by UI or `bpy.ops.colmap_rig.export()`; writes `{out}/rig_config.json` containing an array of rigs where each rig has `cameras` with `image_prefix` and optional `cam_from_rig_rotation` / `cam_from_rig_translation`.
- Render operator: `COLMAP_RIG_OT_render` (bl_idname `colmap_rig.render`) — called by UI or `bpy.ops.colmap_rig.render()`; renders frames start..end for every visible camera and writes files to `{out}/{collection}/{camera}/image{NNNN}.{ext}`.
- UI panel: `COLMAP_RIG_PT_panel` lives in `ui.py`, category `COLMAP Rig` in the 3D Viewport side-bar.

Important scene properties (lookups)
- The code reads scene properties named: `colmap_rig_output_path`, `colmap_rig_image_format`, and `colmap_rig_zero_pad` (used by both export and render). Search shows only usages, not definitions; these properties must be registered elsewhere or set manually in the Blender Python console for testing.

Typical developer workflows
- Quick dev/test in Blender:
  - Copy this folder into Blender's `scripts/addons` (or use Blender's Install Add-on) and enable it in Preferences.
  - In Blender, set the scene properties (output path, image format, zero pad) in the UI panel or via Python:
    - bpy.context.scene.colmap_rig_output_path = '/absolute/path'
    - bpy.context.scene.colmap_rig_image_format = 'JPEG'  # or 'PNG'
    - bpy.context.scene.colmap_rig_zero_pad = 4
  - Run export: `bpy.ops.colmap_rig.export()` — creates `rig_config.json` in output folder.
  - Run render: `bpy.ops.colmap_rig.render()` — writes per-camera image files.

Project-specific patterns & gotchas
- Collections-as-rigs: the exporter iterates `bpy.data.collections` and treats any collection containing visible cameras as a rig. Tests should create collections and set camera `hide_render`/`hide_viewport` appropriately.
- Coordinate flip: exporter flips Y using a matrix before converting to quaternion/translation to match COLMAP conventions — preserve that logic when modifying transforms.
- Register/unregister: modules are expected to expose `register()`/`unregister()` functions. When adding modules, include them in the `modules` tuple in `__init__.py` rather than using dynamic imports.
- Avoid modifying Blender's global state permanently — the render operator saves/restores `scene.camera`, `scene.render.filepath`, and image format.

Examples (copyable)
- Export from Python inside Blender:
  - bpy.ops.colmap_rig.export()
  - Output path: <output>/rig_config.json
- Render from Python inside Blender:
  - bpy.ops.colmap_rig.render()
  - Images: <output>/<CollectionName>/<CameraName>/image0001.jpg (or .png)

Where to look next (for changes or tests)
- Add or find scene property definitions (if you plan to ship defaults or register them) — currently the repo only references them.
- Unit test approach: isolate pure helpers (e.g., matrix->quat/translation conversion) into functions that can be run outside Blender's context, or test inside Blender's background mode if required.

If anything here is unclear or you want more detail (examples for automated tests, CI steps, or a suggested property-registration snippet), tell me which area to expand and I will iterate.
