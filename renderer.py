import bpy
import os
from bpy.types import Operator


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