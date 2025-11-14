# 360_rig_renderer
Blender extension to generate COLMAPs rig_config.json and render the camera rigs from an equirectangular video.


# Known Issues (prob. many more than listed here)
- [ ] User can delete collections and potentially break some functionality
- [ ] Image sequences are imported sparse. Make sure to set the Frame Step' so that only frames with images are actually rendered.
- [ ] implement a 'per camera' resolution. Current work around is to adjust the resolution and render in 'sub-sets'