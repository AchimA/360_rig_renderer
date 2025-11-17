# 360_rig_renderer
Blender extension to generate COLMAPs / GLOMAPs rig_config.json from 360° equirectangular footage and render pinhole cameras.


<img src="images\2025-11-16_Equi2RIG_test.png" alt="User Interface"/>

*Blender UI setup:*
| Position | Description |
| :------------ | :-------- |
| left | acive camera |
| center | 3D view-port with extension in N-Panel |
| right | collections where you add and position cameras as required |

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
  - Media path is used for metadata (type, frame count, resolution) and for camera background in the viewport (not rendered into final frames).
  - Per‑rig resolution is auto‑detected from media and shown read‑only.

## Per‑Rig Resolution
- Each rig has its own `Render Resolution`:
  - Equirect rigs: fields are editable and sync the scene resolution on selection.
  - Perspective rigs: auto‑detected from media and locked; scene resolution syncs on selection.

## Properties & Toggles
- `Include in json`: export this rig to `rig_config.json` (also creates folder structure on render/export).
- `Render`: queue this rig for rendering (projected frames = included cameras × floor((end-start)/step)).
- `Start/End/Step`: timeline per rig; applied in the render operator.
- `Auto‑activate selected camera` (scene): when enabled, selecting a camera sets it active (disabled during batch render).

## EXIF Metadata
- Equirect rigs: Writes EXIF to rendered JPEGs (Make/Model/Software, FocalLength, FocalLengthIn35mmFilm, PixelX/YDimension) to help COLMAP auto-detect intrinsics.
- Perspective rigs: Does not write EXIF by design (avoids misleading metadata for downstream tools).
- Format note: EXIF is only embedded for `JPEG`; other formats (PNG/EXR/TIFF) do not receive EXIF.

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
- [ ] Image sequences are imported sparse. Make sure to set the Frame Step' so that only frames with images are actually rendered.
- [ ] implement a 'per camera' resolution. Current work around is to adjust the resolution and render in 'sub-sets'