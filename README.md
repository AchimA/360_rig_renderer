# 360_rig_renderer
Blender extension to generate COLMAPs / GLOMAPs rig_config.json from 360° equirectangular footage and render pinhole cameras.

## Proposed Workflow
1) For each equirectangular footage / sequence, generate a rig and add cameras as needed. It's usually a good idea to place the cameras such that the person recoding is not visible
2) For normal footage (non equirectangular) add a rig with a single camera and endframe set to -1. This will add a subfolder and adds the rig in the *.json file. You'll then manually have to add the frame sequence to the subfolder.
3) Export the *.json file to your COLMAP / GLOMAP project.
4) Render the frame sequence. The frames are structured in subfolders in the user defined 'output path'.

## Features
- Each rig contains:
    - A movie clip / image sequence
    - lets you define a separate start frame, end frame & frame stepp which is used during rendering
    - rendering automatically adds the subfolder structure expected by COLMAP / GLOMAP

## Current Restrictions
Please don't rename or delete the collections that are handled by the extension. I currently couldn't figure out a way to prevent the user from messing with this.

# Issues / ToDO (prob. many more than listed here)
- [ ] User can delete collections and potentially break some functionality
- [ ] Image sequences are imported sparse. Make sure to set the Frame Step' so that only frames with images are actually rendered.
- [ ] implement a 'per camera' resolution. Current work around is to adjust the resolution and render in 'sub-sets'