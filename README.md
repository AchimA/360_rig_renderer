# 360_rig_renderer
Blender extension to generate COLMAPs / GLOMAPs rig_config.json from 360° equirectangular footage and render pinhole cameras.


<img src="images\2025-11-16_Equi2RIG_test.png" alt="User Interface"/>

*Blender UI setup:*
| Position | Description |
| :------------ | :-------- |
| left | acive camera |
| center | 3D view-port with extension in N-Panel |
| right | collections where you add and position cameras as required |

## Quick Start
- Install the add-on and enable it in Preferences.
- Set output path: Render Properties → Output → set a folder (or in Python: `bpy.context.scene.render.filepath = "D:/output"`).
- Create rigs in the panel `COLMAP Rig`:
  - Equirect rig: add cameras to the rig’s collection; set resolution and frame range.
  - Perspective rig: set Media path; resolution auto-detects and shows read-only.
- Optional toggles per rig: `Include in json`, `Render`, `Write EXIF (JPEG)` (Equirect only), `Render Media via Compositor` (Perspective only).
- Export JSON: run `bpy.ops.colmap_rig.export()` (writes `rig_config.json` in the output folder).
- Render: run `bpy.ops.colmap_rig.render()` (frames in `{output}/{Rig}/{Camera}/imageNNNN.ext`).
- Proceed to COLMAP/GLOMAP with the generated structure.

## Proposed Workflow
I found that 360° footage with *FlowState Stabilization = off* or *Direction Lock* works best. This lets you place the cameras so the operator is not visible in the pinhole views.

1) For each 360° equirect sequence, create an Equirect rig and add cameras as needed (hide cameras you don't want to export/render).
2) For normal footage, create a Perspective rig, point it to your media path, and leave "Render" off if you already have the frames (the rig will still be added to JSON and folders created on export/render).
3) Export the JSON and run COLMAP/GLOMAP using the generated rig structure.
4) Render queued rigs as needed; frames are written into `{output}/{Rig}/{Camera}/imageNNNN.ext`.

Tip: Use the list toggles to include a rig in JSON and/or render. Projected frame counts are shown per rig and as a total.

## Features
- Each rig contains:
    - A movie clip / image sequence
    - lets you define a separate start frame, end frame & frame step which is used during rendering
    - rendering automatically adds the subfolder structure expected by COLMAP / GLOMAP
- Selecting a rig automatically activates the correct world texture and turns on rendered view in the view-port

## Rig Types
- Equirectangular 360° (`EQUIRECT_360`):
  - Multiple cameras inside the rig collection point at an environment texture.
  - Editable per‑rig render resolution.
  - World material is auto-managed per active rig.
- Perspective (`PERSPECTIVE`):
  - Single camera workflow for mixing regular footage.
  - Media path is used for metadata (type, frame count, resolution) and for camera background in the viewport.
  - Optionally renders the media into final frames via compositor when `Render Media via Compositor` is enabled.
  - Per‑rig resolution is auto‑detected from media and shown read‑only.

## Per‑Rig Resolution
- Each rig has its own `Render Resolution`:
  - Equirect rigs: fields are editable and sync the scene resolution on selection.
  - Perspective rigs: auto‑detected from media and locked; scene resolution syncs on selection.

## Properties & Toggles
- `Include in json`: export this rig to `rig_config.json` (also creates folder structure on render/export).
- `Render`: queue this rig for rendering (projected frames = included cameras × floor((end-start)/step)).
- `Start/End/Step`: timeline per rig; applied in the render operator.
- `Write EXIF (JPEG)`: for Equirect rigs, embeds EXIF into JPEG outputs to help COLMAP detect intrinsics.
- `Render Media via Compositor` (Perspective): composites the source media directly into rendered frames.
- `Auto‑activate selected camera` (scene): when enabled, selecting a camera sets it active (disabled during batch render).

## EXIF Metadata
- Equirect rigs: Writes EXIF to rendered JPEGs (Make/Model/Software, FocalLength, FocalLengthIn35mmFilm, PixelX/YDimension) to help COLMAP auto-detect intrinsics.
- Perspective rigs: Does not write EXIF by design (avoids misleading metadata for downstream tools), regardless of the toggle.
- Format note: EXIF is only embedded for `JPEG`; other formats (PNG/EXR/TIFF) do not receive EXIF.

<details>
<summary><h2>Minimal rig_config.json Example</h2></summary>

Below is an illustrative example of the exported structure for one Equirect rig (two cameras) and one Perspective rig (single camera). Camera transforms are relative to the rig; the first visible camera in a rig is the reference sensor.

```json
[
  {
    "rig_name": "EquirectRig",
    "cameras": [
      {
        "image_prefix": "EquirectRig/Cam_A/image",
        "ref_sensor": true
      },
      {
        "image_prefix": "EquirectRig/Cam_B/image",
        "cam_from_rig_rotation": [1.0, 0.0, 0.0, 0.0],
        "cam_from_rig_translation": [0.0, 0.0, 0.0]
      }
    ]
  },
  {
    "rig_name": "PerspectiveRig",
    "cameras": [
      {
        "image_prefix": "PerspectiveRig/Cam_P/image",
        "ref_sensor": true
      }
    ]
  }
]
```

Notes:
- `image_prefix` points to the per-camera subfolder; files are `imageNNNN.ext` with zero padding.
- `ref_sensor` marks the reference camera of the rig; other cameras may include relative rotation (w,x,y,z) and translation (x,y,z).
- Field names and presence may evolve; treat this as a minimal guide rather than a strict schema.

</details>

<details>
<summary><h2>COLMAP / GLOMAP Workflow (PowerShell)</h2></summary>
Example `Workflow.ps1`. Adjust paths and options to your setup.

```powershell
# Set your project and images
$Project = "D:\\MyProject"
$Images  = Join-Path $Project "rendered_frames"   # parent folder containing {Rig}/{Camera}/imageNNNN.ext

$DB      = Join-Path $Project 'database.db'
$RigCfg  = Join-Path $Project 'rig_config.json'
$SparseU = Join-Path $Project 'sparse_unaligned'
$Sparse0 = Join-Path $Project 'sparse\\0'

mkdir $SparseU -Force | Out-Null
mkdir (Split-Path $Sparse0) -Force | Out-Null

# 1) Feature extraction (treat each camera folder as a separate sensor)
# Camera model examples: SIMPLE_PINHOLE | PINHOLE | RADIAL | OPENCV | FULL_OPENCV ...
colmap feature_extractor (
    '--database_path', $DB,
    '--image_path', $Images,
    '--ImageReader.camera_model', 'RADIAL',
    '--ImageReader.single_camera_per_folder', '1',
    '--SiftExtraction.estimate_affine_shape', '1',
    '--SiftExtraction.domain_size_pooling', '1'
)

# 2) Rig configurator (applies rig_config.json to the database; optional but recommended)
if (Test-Path $RigCfg) {
    colmap rig_configurator (
        '--database_path', $DB,
        '--rig_config_path', $RigCfg
    )
}

# 3) Matching (pick ONE)
# Exhaustive (small datasets)
colmap exhaustive_matcher (
    '--database_path', $DB,
    '--FeatureMatching.guided_matching', '1'
)

# OR Sequential (video/temporal)
# colmap sequential_matcher (
#     '--database_path', $DB,
#     '--FeatureMatching.guided_matching', '1',
#     '--SequentialMatching.loop_detection', '1',
#     '--SequentialMatching.loop_detection_period', '10'
# )

# OR Vocab Tree (large datasets; requires a vocab tree file)
# colmap vocab_tree_matcher (
#     '--database_path', $DB,
#     '--FeatureMatching.guided_matching', '1'
# )

# 4) Mapping (pick ONE)
# Global mapping with GLOMAP (fast, recommended)
# glomap mapper (
#     '--database_path', $DB,
#     '--image_path', $Images,
#     '--output_path', $SparseU
# )

# OR Incremental mapping with COLMAP (slower, more robust for complex scenes)
colmap mapper (
    '--database_path', $DB,
    '--image_path', $Images,
    '--output_path', $SparseU
)

# 5) Orientation alignment (COLMAP)
colmap model_orientation_aligner (
    '--input_path', (Join-Path $SparseU '0'),
    '--output_path', $Sparse0,
    '--image_path', $Images
)

# (Optional) Undistort if needed for downstream tools/viewers
# colmap image_undistorter (
#     '--image_path', $Images,
#     '--input_path', $Sparse0,
#     '--output_path', $Sparse0,
#     '--output_type', 'COLMAP'
# )

# (Optional) Launch GUI to inspect results
# colmap gui (
#     '--database_path', $DB,
#     '--import_path', $Sparse0,
#     '--image_path', $Images
# )
```

Notes:
- Use `--ImageReader.single_camera_per_folder 1` so each `{Rig}/{Camera}` folder acts as a separate sensor; `rig_configurator` then enforces rig constraints from `rig_config.json`.
- Prefer Exhaustive for small sets; Sequential for continuous video; Vocab Tree for large sets (requires a vocab tree file).
- This flow mirrors `SparseWorkflow.ps1` (feature → rig_configurator → match → GLOMAP mapper → orientation align). Dense reconstruction is intentionally omitted here.

</details>

## Current Restrictions
Please don't rename or delete the collections that are handled by the extension. I currently couldn't figure out a way to prevent the user from messing with this.

## Third-Party Libraries

This extension bundles the following third-party libraries:

- **piexif** v1.1.3 - MIT License - https://github.com/hMatoba/Piexif
  - Used for writing EXIF metadata (focal length, sensor size) to rendered JPEG images
  - Enables COLMAP to automatically detect camera parameters from image files
  - License: See `wheels/LICENSE-piexif.txt`

# Issues / ToDO (prob. many more than listed here)
- [ ] User can delete collections and potentially break some functionality
- [ ] Image sequences are imported **sparse**. Make sure to set the Frame Step' so that only frames with images are actually rendered.
- [x] implement a 'per camera' resolution. Current work around is to adjust the resolution and render in 'sub-sets'