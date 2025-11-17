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
I found that 360° footage with *'FlowState Stabilization' = off* or 
*'Direction Lock'* works best. This let's you place ca
eras, such that the person recoding is not visible in the pinhole cameras.

1) For each equirectangular footage / sequence, generate a rig and add cameras as needed. It's usually a good idea to place the cameras such that the person recoding is not visible
2) For normal footage (non equirectangular) add a rig with a single camera and end-frame set to -1. This will add a subfolder and adds the rig in the *.json file. You'll then manually have to add the frame sequence to the subfolder.
3) Export the *.json file to your COLMAP / GLOMAP project.
4) Render the frame sequence. The frames are structured in sub-folders in the user defined 'output path'.

## Features
- Each rig contains:
    - A movie clip / image sequence
    - lets you define a separate start frame, end frame & frame step which is used during rendering
    - rendering automatically adds the subfolder structure expected by COLMAP / GLOMAP
- Selecting a rig automatically activates the correct world texture and turns on rendered view in the view-port

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