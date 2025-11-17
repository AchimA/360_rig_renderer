import bpy
import os
import re
from pathlib import Path
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
        # Preserve original compositor state and link (if any)
        orig_use_nodes = scene.use_nodes
        original_composite_link = None
        comp_tree = None
        try:
            comp_tree = scene.node_tree if scene.use_nodes and scene.node_tree else None
            if comp_tree:
                comp_node = next((n for n in comp_tree.nodes if n.type == 'COMPOSITE'), None)
                if comp_node and comp_node.inputs and comp_node.inputs[0].is_linked:
                    link = comp_node.inputs[0].links[0]
                    original_composite_link = (link.from_node.name, link.from_socket.name, comp_node.name, comp_node.inputs[0].name)
        except Exception:
            pass
        
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
            
            # Set world per rig type (ensure equirect rigs use their world, perspective uses none)
            try:
                if getattr(rig_item, 'rig_type', 'EQUIRECT_360') == 'EQUIRECT_360':
                    world_name = f"World_{rig_item.name}"
                    if world_name in bpy.data.worlds:
                        scene.world = bpy.data.worlds[world_name]
                else:
                    scene.world = None
            except Exception:
                pass

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
                    # Configure compositor for Perspective rigs if requested
                    try:
                        rig_type = getattr(rig_item, 'rig_type', 'EQUIRECT_360')
                        use_comp = getattr(rig_item, 'use_compositor_media', False)
                        src_path = getattr(rig_item, 'source_filepath', '')
                    except Exception:
                        rig_type, use_comp, src_path = 'EQUIRECT_360', False, ''

                    if rig_type == 'PERSPECTIVE' and use_comp and src_path:
                        scene.use_nodes = True
                        if not scene.node_tree:
                            scene.node_tree = bpy.data.node_groups.new('Compositing', 'CompositorNodeTree')
                        nt = scene.node_tree
                        # Ensure composite node exists
                        comp = next((n for n in nt.nodes if n.type == 'COMPOSITE'), None)
                        if not comp:
                            comp = nt.nodes.new('CompositorNodeComposite')
                            comp.location = (400, 0)
                        src_type = getattr(rig_item, 'source_type', '')
                        # Use Movie Clip node for videos
                        if src_type == 'Movie Clip':
                            clip_node = next((n for n in nt.nodes if n.name == 'RIG_MEDIA_CLIP' and n.type == 'MOVIECLIP'), None)
                            if not clip_node:
                                clip_node = nt.nodes.new('CompositorNodeMovieClip')
                                clip_node.name = 'RIG_MEDIA_CLIP'
                                clip_node.label = 'RIG_MEDIA_CLIP'
                                clip_node.location = (0, -120)
                            try:
                                clip = bpy.data.movieclips.load(src_path, check_existing=True)
                                clip_node.clip = clip
                                # Clear composite input links
                                while comp.inputs and comp.inputs[0].is_linked:
                                    nt.links.remove(comp.inputs[0].links[0])
                                nt.links.new(clip_node.outputs.get('Image'), comp.inputs[0])
                            except Exception as e:
                                print(f'Warning: compositor movie clip load failed: {e}')
                        else:
                            # Image node; for sequences, swap image per frame
                            img_node = next((n for n in nt.nodes if n.name == 'RIG_MEDIA_IMAGE' and n.type == 'IMAGE'), None)
                            if not img_node:
                                img_node = nt.nodes.new('CompositorNodeImage')
                                img_node.name = 'RIG_MEDIA_IMAGE'
                                img_node.label = 'RIG_MEDIA_IMAGE'
                                img_node.location = (0, 0)
                            try:
                                frame_path = src_path
                                if src_type == 'Image Sequence':
                                    p = Path(src_path)
                                    stem = p.stem
                                    m = re.match(r'(.+?)(\d+)$', stem)
                                    if m:
                                        base, digits = m.groups()
                                        pad = len(digits)
                                        frame_name = f"{base}{str(frame).zfill(pad)}{p.suffix}"
                                        fp = Path(p.parent) / frame_name
                                        if fp.exists():
                                            frame_path = str(fp)
                                img = bpy.data.images.load(frame_path, check_existing=True)
                                img.source = 'FILE'
                                img_node.image = img
                                # Clear composite input links
                                while comp.inputs and comp.inputs[0].is_linked:
                                    nt.links.remove(comp.inputs[0].links[0])
                                nt.links.new(img_node.outputs.get('Image'), comp.inputs[0])
                            except Exception as e:
                                print(f'Warning: compositor image load failed: {e}')
                    else:
                        # Disable compositor for non-composited passes
                        scene.use_nodes = False

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
                    
                    # Write EXIF data to JPEG files only if enabled and rig is not Perspective
                    try:
                        rig_type = getattr(rig_item, 'rig_type', 'EQUIRECT_360')
                        write_exif = getattr(rig_item, 'write_exif', True)
                    except Exception:
                        rig_type, write_exif = 'EQUIRECT_360', True
                    if rig_type != 'PERSPECTIVE' and write_exif:
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
        # Restore compositor link/state
        try:
            if original_composite_link and scene.node_tree:
                nt = scene.node_tree
                from_node_name, from_socket_name, comp_name, comp_input_name = original_composite_link
                comp = nt.nodes.get(comp_name)
                from_node = nt.nodes.get(from_node_name)
                if comp and from_node:
                    # Clear current link
                    if comp.inputs and comp.inputs[0].is_linked:
                        nt.links.remove(comp.inputs[0].links[0])
                    nt.links.new(from_node.outputs.get(from_socket_name), comp.inputs[0])
        except Exception:
            pass
        scene.use_nodes = orig_use_nodes
        
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