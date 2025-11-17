# Perspective Rig Support

## Overview
The extension now supports two rig types for mixing equirectangular 360° footage with regular perspective footage for COLMAP reconstruction.

## Rig Types

### 1. Equirectangular 360° (Default)
- **Use case**: 360° video/images (equirectangular projection)
- **Setup**: Multiple static cameras view a spherical environment texture
- **World material**: Movie clip mapped to environment sphere
- **JSON export**: Multiple cameras with relative transforms
- **Preview**: Rendered viewport shows cameras viewing the sphere

### 2. Perspective
- **Use case**: Regular video/images (perspective projection)
- **Setup**: Single camera with movie clip as background image
- **World material**: None (clip is camera background)
- **JSON export**: Single-camera rig (reference sensor only)
- **Preview**: Rendered viewport shows camera background

## Workflow

### Creating a Perspective Rig

1. Add a new rig in Rig Manager
2. Set **Rig Type** to "Perspective"
3. Browse and select your movie clip or image sequence
4. Click **"Create Camera"** button (appears if no camera exists)
5. The camera will be created at origin with the clip as background

### JSON Export Behavior

**Equirect 360° rig** with 5 cameras exports as:
```json
{
  "cameras": [
    {"image_prefix": "Rig_0/F_L/", "ref_sensor": true},
    {"image_prefix": "Rig_0/F_R/", "cam_from_rig_rotation": [...], ...},
    {"image_prefix": "Rig_0/F_O/", "cam_from_rig_rotation": [...], ...},
    {"image_prefix": "Rig_0/R_R/", "cam_from_rig_rotation": [...], ...},
    {"image_prefix": "Rig_0/R_L/", "cam_from_rig_rotation": [...], ...}
  ]
}
```

**Perspective rig** with 1 camera exports as:
```json
{
  "cameras": [
    {"image_prefix": "Rig_1/Rig_1_Camera/", "ref_sensor": true}
  ]
}
```

### Mixed Reconstruction Example

```
Project/
├── rig_config.json          # Contains both rig types
├── Rig_0/                   # Equirect 360° rig
│   ├── F_L/
│   │   ├── Rig_0_image0001.jpg
│   │   └── ...
│   ├── F_R/
│   └── ... (5 camera folders)
├── Rig_1/                   # Perspective rig
│   └── Rig_1_Camera/
│       ├── Rig_1_image0001.jpg
│       └── ...
```

COLMAP will:
1. Recognize both as rigs with shared intrinsics per frame
2. Match features across all images (from both rigs)
3. Reconstruct the full scene with mixed camera types

## Implementation Details

### New Properties
- `RigItem.rig_type`: Enum selecting 'EQUIRECT_360' or 'PERSPECTIVE'

### New Functions
- `create_perspective_camera()`: Creates camera with clip as background
- `update_rig_type()`: Handles switching between rig types

### Modified Functions
- `create_or_update_world_material()`: Only creates world for equirect rigs
- `update_media_info()`: Creates appropriate setup based on rig type
- `update_collection_visibility()`: Conditional world material assignment

### New Operator
- `RIG_OT_create_perspective_camera`: Manual camera creation button

## Camera Background Setup

For perspective rigs, the camera background image is configured with:
- Image source type (FILE, MOVIE, or SEQUENCE)
- Frame sync (for animated sources)
- Full opacity, behind scene geometry
- Stretch or fit to frame

## EXIF Data

Both rig types write EXIF metadata to rendered JPEG images:
- Focal length (from Blender camera)
- Sensor width (from Blender camera)
- 35mm equivalent focal length
- Image dimensions

This helps COLMAP detect camera intrinsics automatically.
