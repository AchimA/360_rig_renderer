import bpy
import os
from bpy.types import Operator

try:
    import piexif
    PIEXIF_AVAILABLE = True
except ImportError:
    PIEXIF_AVAILABLE = False
    print("Warning: piexif not available, EXIF data will not be written to images")


def write_camera_exif(image_path, camera_obj, scene):
    """Write EXIF metadata to JPEG images for COLMAP camera parameter detection."""
    if not PIEXIF_AVAILABLE:
        return
    
    # Only write EXIF to JPEG files
    if not (image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg')):
        return
    
    try:
        camera_data = camera_obj.data
        
        # Get camera parameters
        focal_mm = camera_data.lens  # Focal length in mm
        sensor_width_mm = camera_data.sensor_width  # Sensor width in mm
        image_width_px = scene.render.resolution_x
        image_height_px = scene.render.resolution_y
        
        # Calculate 35mm equivalent focal length
        focal_35mm = int((focal_mm / sensor_width_mm) * 36.0)
        
        # Create EXIF data
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: "Blender",
                piexif.ImageIFD.Model: "Virtual Camera",
                piexif.ImageIFD.Software: f"Blender {bpy.app.version_string}",
            },
            "Exif": {
                piexif.ExifIFD.FocalLength: (int(focal_mm * 100), 100),  # Store as rational (numerator, denominator)
                piexif.ExifIFD.FocalLengthIn35mmFilm: focal_35mm,
                piexif.ExifIFD.PixelXDimension: image_width_px,
                piexif.ExifIFD.PixelYDimension: image_height_px,
            },
        }
        
        # Insert EXIF data into the image
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        
    except Exception as e:
        print(f"Warning: Failed to write EXIF data to {image_path}: {e}")


class COLMAP_RIG_OT_render(Operator):
    bl_idname = 'colmap_rig.render'
    bl_label = 'Render all rigs to folders'
    bl_description = 'Render frames for cameras in rig collections based on rig item settings (ESC to cancel between frames)'

    def execute(self, context):
        
        scene = context.scene
        
        # Use render output path (// resolves to blend file directory)
        out_base = bpy.path.abspath(scene.render.filepath)
        if not out_base:
            self.report({'WARNING'}, 'No render output path set')
            return {'CANCELLED'}
        
        # Check if rig_collection exists
        if not hasattr(scene, 'rig_collection'):
            self.report({'WARNING'}, 'No rig collection found in scene')
            return {'CANCELLED'}
        
        # Initialize progress
        context.window_manager.progress_begin(0, 100)
        
        # Store original settings
        original_camera = scene.camera
        orig_filepath = scene.render.filepath
        orig_frame_start = scene.frame_start
        orig_frame_end = scene.frame_end
        orig_frame_step = scene.frame_step
        orig_resolution_x = scene.render.resolution_x
        orig_resolution_y = scene.render.resolution_y
        
        # Temporarily disable auto-camera-switching during rendering
        orig_sel_cam_active = scene.sel_cam_active
        scene.sel_cam_active = False
        
        rendered_count = 0
        total_frames = 0
        
        # Calculate total frames to render for progress tracking
        total_frames_to_render = 0
        for rig_item in scene.rig_collection:
            if not rig_item.do_render or not rig_item.collection:
                continue
            cams = [obj for obj in rig_item.collection.objects if obj.type == 'CAMERA' and not obj.hide_render]
            if cams:
                frames_in_range = len(range(rig_item.start_frame, rig_item.end_frame + 1, rig_item.frame_step))
                total_frames_to_render += frames_in_range * len(cams)
        
        if total_frames_to_render == 0:
            self.report({'WARNING'}, 'No frames to render')
            return {'CANCELLED'}
        
        current_frame_index = 0
        
        # Process each rig item
        for rig_item in scene.rig_collection:
            # Skip if collection doesn't exist
            if not rig_item.collection or rig_item.collection.name not in bpy.data.collections:
                continue
            
            # Apply this rig's resolution settings
            scene.render.resolution_x = rig_item.render_resolution[0]
            scene.render.resolution_y = rig_item.render_resolution[1]
            
            coll = rig_item.collection
            
            # Get cameras that are not disabled in renders
            cams = [
                obj for obj in coll.objects
                if obj.type == 'CAMERA' and not obj.hide_render
            ]
            
            if not cams:
                continue
            
            # Create folder structure if include_in_json is True
            if rig_item.include_in_json:
                for cam in cams:
                    cam_folder = os.path.join(out_base, rig_item.name, cam.name)
                    os.makedirs(cam_folder, exist_ok=True)
            
            # Only render if do_render is True
            if not rig_item.do_render:
                continue
            
            # Use rig item's frame settings
            start = rig_item.start_frame
            end = rig_item.end_frame
            step = rig_item.frame_step
            
            # Render frames
            for frame in range(start, end + 1, step):
                scene.frame_set(frame)
                
                for cam in cams:
                    current_frame_index += 1
                    progress = (current_frame_index / total_frames_to_render) * 100
                    
                    # Update progress in console and UI
                    print(f"Rendering {current_frame_index}/{total_frames_to_render} ({progress:.1f}%) - {rig_item.name}/{cam.name} frame {frame}")
                    context.window_manager.progress_update(current_frame_index / total_frames_to_render * 100)
                    # Construct output path
                    cam_folder = os.path.join(out_base, rig_item.name, cam.name)
                    
                    # Determine file extension from render settings
                    file_format = scene.render.image_settings.file_format
                    if file_format == 'JPEG':
                        ext = 'jpg'
                    elif file_format == 'PNG':
                        ext = 'png'
                    elif file_format == 'OPEN_EXR':
                        ext = 'exr'
                    elif file_format == 'TIFF':
                        ext = 'tif'
                    else:
                        ext = 'png'  # fallback
                    
                    # Use 4-digit zero padding with rig_name prefix
                    filename = f'{rig_item.name}_image{str(frame).zfill(4)}.{ext}'
                    filepath = os.path.join(cam_folder, filename)
                    
                    # Set scene camera and render
                    scene.camera = cam
                    scene.render.filepath = filepath
                    
                    bpy.ops.render.render(write_still=True)
                    
                    # Write EXIF data to JPEG files for non-Perspective rigs only
                    try:
                        rig_type = getattr(rig_item, 'rig_type', 'EQUIRECT_360')
                    except Exception:
                        rig_type = 'EQUIRECT_360'
                    if rig_type != 'PERSPECTIVE':
                        write_camera_exif(filepath, cam, scene)
                    
                    total_frames += 1
            
            rendered_count += 1
        
        # End progress
        context.window_manager.progress_end()
        
        # Restore original settings
        scene.camera = original_camera
        scene.render.filepath = orig_filepath
        scene.frame_start = orig_frame_start
        scene.frame_end = orig_frame_end
        scene.frame_step = orig_frame_step
        scene.render.resolution_x = orig_resolution_x
        scene.render.resolution_y = orig_resolution_y
        scene.sel_cam_active = orig_sel_cam_active
        
        if rendered_count == 0:
            self.report({'WARNING'}, 'No rigs marked for rendering')
            return {'CANCELLED'}
        
        self.report({'INFO'}, f'Rendered {total_frames} frames for {rendered_count} rigs into {out_base}')
        return {'FINISHED'}

classes = (
    COLMAP_RIG_OT_render,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)