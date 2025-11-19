#rig_manager.py
import bpy
import os
import math
import pathlib
import re

# Rig Item Property Group
class RigItem(bpy.types.PropertyGroup):
    ID: bpy.props.IntProperty(
        name = 'ID',
        default = 0
        )
    name: bpy.props.StringProperty(
    name = 'Rig Name',
    default = 'Rig ###',
    update = lambda self, context: update_world_name(self, context)
    )
    sel_cam_active: bpy.props.BoolProperty(
        name = 'Activate Selected Camera',
        description = 'Automatically set the selected camera as the active scene camera',
        default = True
    )
    # Pointer to the managed collection in the scene
    collection: bpy.props.PointerProperty(
        name = 'Rig Collection',
        type = bpy.types.Collection,
        description = 'The Blender collection managed by this rig item'
    )
    # Rig type: equirectangular 360 or perspective
    rig_type: bpy.props.EnumProperty(
        name = 'Rig Type',
        description = 'Type of rig rendering',
        items = [
            ('EQUIRECT_360', 'Equirectangular 360°', 'Multiple cameras viewing spherical environment (for 360° footage)'),
            ('PERSPECTIVE', 'Perspective', 'Single camera with movie clip as background (for regular footage)'),
        ],
        default = 'EQUIRECT_360',
        update = lambda self, context: update_rig_type(self, context)
    )
    # Path to movie clip or image sequence
    source_filepath: bpy.props.StringProperty(
        name = 'Source Path',
        description = 'Path to the Movie Clip or Image Sequence',
        default = '',
        update = lambda self, context: update_media_info(self, context)
    )
    # Auto-detected source type (read-only)
    source_type: bpy.props.StringProperty(
        name = 'Source Type',
        default = 'Unknown',
        description='Auto-detected media type'
    )
    media_frame_count: bpy.props.IntProperty(
        name = 'Media Frame Count',
        default = 0,
        min = 0,
    )
    # Rendering parameters
    start_frame: bpy.props.IntProperty(
        name = 'Start Frame',
        default = 1,
        min = 1,
        update = lambda self, context: sync_frame_range_to_scene(self, context)
    )
    end_frame: bpy.props.IntProperty(
        name = 'End Frame',
        default = -1,
        min = -1,
        update = lambda self, context: sync_frame_range_to_scene(self, context)
    )
    frame_step: bpy.props.IntProperty(
        name = 'Frame Step',
        default = 10,
        min = 1,
        update = lambda self, context: sync_frame_range_to_scene(self, context)
    )
    num_cameras: bpy.props.IntProperty(
        name = 'Number of Cameras',
        default = 0,
        min = 0
    )
    num_inkl_cameras: bpy.props.IntProperty(
        name = 'Number of Included Cameras',
        default = 0,
        min = 0
    )
    # Render resolution per rig
    render_resolution: bpy.props.IntVectorProperty(
        name = 'Render Resolution',
        description = 'Render resolution (width, height) for this rig',
        default = (2048, 1080),
        size = 2,
        min = 64,
        max = 65536,
        subtype = 'XYZ',
        update = lambda self, context: sync_rig_resolution_to_scene(self, context)
    )
    # Boolean toggles for workflow
    include_in_json: bpy.props.BoolProperty(
        name = 'Include in json',
        description = 'Include this rig in the exported json config',
        default = True
    )
    do_render: bpy.props.BoolProperty(
        name = 'Render',
        description = 'Include this rig in batch rendering',
        default = True
    )
    write_exif: bpy.props.BoolProperty(
        name = 'Write EXIF (JPEG)',
        description = 'Embed camera EXIF metadata into rendered JPEG files (ignored for non-JPEG formats and perspective rigs)',
        default = True
    )
    use_compositor_media: bpy.props.BoolProperty(
        name = 'Render Media via Compositor',
        description = 'For Perspective rigs: composite the media (movie/sequence) directly to the output frames',
        default = True
    )


###########################################################################
### Helper Functions #####################################################
###########################################################################

def sync_frame_range_to_scene(rig_item, context):
    """Update scene frame range when rig item frame properties change (if it's the active rig)."""
    scene = context.scene
    if hasattr(scene, 'rig_collection') and hasattr(scene, 'rig_index'):
        if 0 <= scene.rig_index < len(scene.rig_collection):
            if scene.rig_collection[scene.rig_index] == rig_item:
                # This is the active rig, update scene timeline
                scene.frame_start = rig_item.start_frame
                scene.frame_end = rig_item.end_frame
                scene.frame_step = rig_item.frame_step

def sync_rig_resolution_to_scene(rig_item, context):
    """Update scene render resolution when rig resolution changes (if it's the active rig)."""
    scene = context.scene
    if hasattr(scene, 'rig_collection') and hasattr(scene, 'rig_index'):
        if 0 <= scene.rig_index < len(scene.rig_collection):
            if scene.rig_collection[scene.rig_index] == rig_item:
                # This is the active rig, update scene render resolution
                scene.render.resolution_x = rig_item.render_resolution[0]
                scene.render.resolution_y = rig_item.render_resolution[1]

def ensure_rig_config_collection():
    """Ensure the 'rig_config' parent collection exists and is linked to the scene."""
    parent_name = 'rig_config'
    if parent_name in bpy.data.collections:
        parent_coll = bpy.data.collections[parent_name]
    else:
        parent_coll = bpy.data.collections.new(parent_name)
        bpy.context.scene.collection.children.link(parent_coll)
    return parent_coll

def projected_frames_for_rig(rig_item: bpy.types.PropertyGroup) -> int:
    """Compute projected frames to render for a single rig.

    Uses the formula requested: num_inkl_cameras * floor((end_frame - start_frame)/frame_step).
    Returns 0 if values are not valid.
    """
    try:
        # Respect do_render flag
        if not getattr(rig_item, 'do_render', False):
            return 0
        step = int(rig_item.frame_step)
        if step <= 0:
            return 0
        # floor division; clamp at 0 in case end < start
        frame_span = int(rig_item.end_frame) - int(rig_item.start_frame)
        per_camera = max(0, frame_span // step)
        return int(rig_item.num_inkl_cameras) * per_camera
    except Exception:
        return 0

def create_perspective_camera(rig_item, context):
    """Create a single camera for perspective rig with movie clip as background."""
    if not rig_item.collection:
        create_rig_collection(rig_item)
    
    coll = rig_item.collection
    scene = context.scene
    
    # Create camera object
    cam_data = bpy.data.cameras.new(f"{rig_item.name}_Camera")
    cam_obj = bpy.data.objects.new(f"{rig_item.name}_Camera", cam_data)
    
    # Link to collection
    coll.objects.link(cam_obj)
    
    # Position at origin, looking down -Z (Blender's default camera direction)
    cam_obj.location = (0, 0, 0)
    cam_obj.rotation_euler = (0, 0, 0)
    
    # Set up camera background image if media exists
    if rig_item.source_filepath and rig_item.source_filepath.strip():
        try:
            set_camera_background_image_for_perspective(rig_item, cam_obj)
        except Exception as e:
            print(f"Error setting up camera background image: {e}")
    
    return cam_obj

def create_rig_collection(rig_item):
    """Create a new collection for the given rig_item under rig_config."""
    parent_coll = ensure_rig_config_collection()
    coll_name = rig_item.name
    # Create new collection
    new_coll = bpy.data.collections.new(coll_name)
    parent_coll.children.link(new_coll)
    # Store reference in the rig item
    rig_item.collection = new_coll
    return new_coll

def remove_rig_collection(rig_item):
    """Remove the collection associated with the rig_item."""
    if rig_item.collection:
        coll = rig_item.collection
        # Unlink from rig_config parent if present
        if 'rig_config' in bpy.data.collections:
            parent_coll = bpy.data.collections['rig_config']
            if coll.name in parent_coll.children:
                parent_coll.children.unlink(coll)
        # Remove the collection data
        bpy.data.collections.remove(coll)
        rig_item.collection = None

def create_or_update_world_material(rig_item):
    """Create or update world material with environment texture for the rig.
    Only creates world material for EQUIRECT_360 rigs."""
    
    # Only create world material for equirect rigs
    if rig_item.rig_type != 'EQUIRECT_360':
        return None
    
    world_name = f"World_{rig_item.name}"
    
    # Get or create world
    if world_name in bpy.data.worlds:
        world = bpy.data.worlds[world_name]
    else:
        world = bpy.data.worlds.new(world_name)
    
    # Enable nodes
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    
    # Clear existing nodes
    nodes.clear()
    
    # Create nodes
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (0, 0)
    
    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (200, 0)
    # Rotate environment by 90 degrees around Z
    mapping.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(90.0))
    
    env_tex = nodes.new(type='ShaderNodeTexEnvironment')
    env_tex.location = (400, 0)
    
    # Set image/movie if filepath exists
    if rig_item.source_filepath and rig_item.source_filepath.strip():
        try:
            # Load image or movie - always load to ensure we have the latest
            img = bpy.data.images.load(rig_item.source_filepath, check_existing=True)
            
            # Set image source type BEFORE assigning to texture
            if rig_item.source_type == 'Movie Clip':
                img.source = 'MOVIE'
            elif rig_item.source_type == 'Image Sequence':
                img.source = 'SEQUENCE'
            else:
                img.source = 'FILE'
            
            # Assign image to texture
            env_tex.image = img
            
            # Configure image_user for animated textures
            if rig_item.source_type in ['Movie Clip', 'Image Sequence']:
                env_tex.image_user.use_auto_refresh = True
                env_tex.image_user.use_cyclic = False
                env_tex.image_user.frame_start = 1
                if rig_item.media_frame_count > 0:
                    env_tex.image_user.frame_duration = rig_item.media_frame_count
                    env_tex.image_user.frame_offset = 0
            
        except Exception as e:
            print(f"Error loading image for world material: {e}")
    
    background = nodes.new(type='ShaderNodeBackground')
    background.location = (600, 0)
    
    output = nodes.new(type='ShaderNodeOutputWorld')
    output.location = (800, 0)
    
    # Create links
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
    links.new(env_tex.outputs['Color'], background.inputs['Color'])
    links.new(background.outputs['Background'], output.inputs['Surface'])
    
    return world

def set_camera_background_image_for_perspective(rig_item, cam_obj):
    """Attach or update the camera background image for a perspective rig camera.
    This is viewport-only; it does not render into final frames.
    """
    filepath = rig_item.source_filepath
    if not filepath:
        return

    img = bpy.data.images.load(filepath, check_existing=True)

    if rig_item.source_type == 'Movie Clip':
        img.source = 'MOVIE'
    elif rig_item.source_type == 'Image Sequence':
        img.source = 'SEQUENCE'
    else:
        img.source = 'FILE'

    cam_data = cam_obj.data
    cam_data.show_background_images = True

    # Reuse first slot if present, otherwise create a new one
    bg = cam_data.background_images[0] if cam_data.background_images else cam_data.background_images.new()
    bg.image = img
    bg.alpha = 1.0
    bg.display_depth = 'BACK'
    if rig_item.source_type in ['Movie Clip', 'Image Sequence']:
        bg.frame_method = 'STRETCH'
        bg.image_user.use_auto_refresh = True
        bg.image_user.use_cyclic = False
        bg.image_user.frame_start = 1
        if rig_item.media_frame_count > 0:
            bg.image_user.frame_duration = rig_item.media_frame_count

def remove_world_material(rig_item):
    """Remove the world material associated with the rig_item."""
    world_name = f"World_{rig_item.name}"
    if world_name in bpy.data.worlds:
        world = bpy.data.worlds[world_name]
        bpy.data.worlds.remove(world)

def update_rig_type(rig_item, context):
    """Handle rig type changes: switch between equirect and perspective rendering."""
    if rig_item.rig_type == 'PERSPECTIVE':
        # For perspective rigs, create a single camera if none exists
        if rig_item.collection:
            cams = [obj for obj in rig_item.collection.objects if obj.type == 'CAMERA']
            if not cams and rig_item.source_filepath:
                # Auto-create camera for perspective rig
                create_perspective_camera(rig_item, context)
        # Perspective rigs do not write EXIF by default
        rig_item.write_exif = False
        rig_item.use_compositor_media = True
    else:
        # Equirect mode - ensure world material exists
        if rig_item.source_filepath:
            create_or_update_world_material(rig_item)
        rig_item.use_compositor_media = False

def update_world_name(rig_item, context):
    """Rename the world material and collection when rig name changes."""
    scene = context.scene
    new_world_name = f"World_{rig_item.name}"
    
    # Rename collection if it exists
    if rig_item.collection and rig_item.collection.name in bpy.data.collections:
        rig_item.collection.name = rig_item.name
    
    # If world with new name already exists, we're done
    if new_world_name in bpy.data.worlds:
        return
    
    # Find worlds that start with "World_" but don't match any current rig name
    current_rig_world_names = {f"World_{item.name}" for item in scene.rig_collection}
    
    for world in bpy.data.worlds:
        if world.name.startswith("World_") and world.name not in current_rig_world_names:
            # Found an orphaned world - rename it to match this rig
            world.name = new_world_name
            break

def update_media_info(rig_item, context):
    """Auto-detect media type and update frame count when source_filepath changes."""
    
    filepath = rig_item.source_filepath
    if not filepath:
        rig_item.source_type = 'Unknown'
        rig_item.media_frame_count = 0
        return
    
    path = pathlib.Path(filepath)
    
    # Valid extensions
    MOVIE_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.mpeg', '.mpg'}
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff', '.bmp', '.tga', '.dpx'}
    
    if not path.exists():
        print(f"Warning: File does not exist: {filepath}")
        rig_item.source_type = 'File not found'
        return
    
    ext = path.suffix.lower()
    
    # Auto-detect type based on extension
    if ext in MOVIE_EXTS:
        rig_item.source_type = 'Movie Clip'
        
        # Try to get movie clip frame count
        try:
            # Load movie clip temporarily to get frame count
            clip = bpy.data.movieclips.load(filepath)
            frame_count = clip.frame_duration
            bpy.data.movieclips.remove(clip)
            
            rig_item.media_frame_count = frame_count
            rig_item.end_frame = frame_count
            print(f"Movie clip loaded: {frame_count} frames")
        except Exception as e:
            print(f"Error loading movie clip: {e}")
        # No manual override; use detected frame count
    
    elif ext in IMAGE_EXTS:
        # For image sequences, count files with frame numbers in the same directory
        parent = path.parent
        stem = path.stem
        
        # Try to detect sequence pattern (e.g., image_0001.png -> image_####.png)
        match = re.match(r'(.+?)(\d+)$', stem)
        if match:
            rig_item.source_type = 'Image Sequence'
            base_name, frame_num = match.groups()
            pad_length = len(frame_num)
            
            # Count files matching pattern
            count = 0
            for file in parent.glob(f"{base_name}*{ext}"):
                if re.match(rf'{re.escape(base_name)}\d{{{pad_length}}}{re.escape(ext)}$', file.name):
                    count += 1
            
            if count > 0:
                rig_item.media_frame_count = count
                rig_item.end_frame = count
                print(f"Image sequence detected: {count} frames")
                # No manual override; use detected sequence count
        else:
            rig_item.source_type = 'Single Image'
            rig_item.media_frame_count = 1
            rig_item.end_frame = 1
    else:
        rig_item.source_type = 'Unknown format'
        print(f"Warning: Unsupported file extension '{ext}'")
    
    # Create appropriate setup based on rig type
    if rig_item.rig_type == 'EQUIRECT_360':
        # Create or update world material with the media
        create_or_update_world_material(rig_item)
    elif rig_item.rig_type == 'PERSPECTIVE':
        # Ensure a perspective camera exists
        if rig_item.collection:
            cams = [obj for obj in rig_item.collection.objects if obj.type == 'CAMERA']
            if not cams:
                create_perspective_camera(rig_item, bpy.context)
            else:
                # Update background image on the existing camera
                try:
                    set_camera_background_image_for_perspective(rig_item, cams[0])
                except Exception as e:
                    print(f"Warning: Could not set camera background image: {e}")
        # Update rig resolution from media (update callback handles scene sync)
        try:
            img = bpy.data.images.load(filepath, check_existing=True)
            width = int(img.size[0]) if img.size[0] else 0
            height = int(img.size[1]) if img.size[1] else 0
            if width > 0 and height > 0:
                # Respect minimum of 64; update callback syncs to scene automatically
                rig_item.render_resolution = (max(64, width), max(64, height))
        except Exception as e:
            print(f"Warning: Could not load media to detect resolution: {e}")

def update_collection_visibility(scene):
    """Show only the active rig collection in viewport, hide all others, and set it as active."""
    if not hasattr(scene, 'rig_collection') or not hasattr(scene, 'rig_index'):
        return
    
    idx = scene.rig_index
    if idx < 0 or idx >= len(scene.rig_collection):
        return
    
    # Get the active rig item
    active_item = scene.rig_collection[idx]
    
    # Update visibility for all rig collections
    for i, item in enumerate(scene.rig_collection):
        if item.collection and item.collection.name in bpy.data.collections:
            coll = item.collection
            # Show only the active collection
            coll.hide_viewport = (i != idx)
            
            # Set the active collection in the view layer and activate first camera
            if i == idx:
                try:
                    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children['rig_config'].children[coll.name]
                except (KeyError, AttributeError):
                    pass  # Collection not found in view layer hierarchy
                
                # Set first camera in collection as active scene camera
                cameras = [obj for obj in coll.objects if obj.type == 'CAMERA']
                if cameras:
                    scene.camera = cameras[-1]
                
                # Switch world material to this rig's world (only for equirect rigs)
                if item.rig_type == 'EQUIRECT_360':
                    world_name = f"World_{item.name}"
                    if world_name in bpy.data.worlds:
                        scene.world = bpy.data.worlds[world_name]
                else:
                    # For perspective rigs, clear the world material
                    scene.world = None
                
                # Set all 3D viewports to RENDERED shading mode
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            for space in area.spaces:
                                if space.type == 'VIEW_3D':
                                    space.shading.type = 'RENDERED'
                
                # Update timeline and render settings from active rig item
                scene.frame_start = item.start_frame
                scene.frame_end = item.end_frame
                scene.frame_step = item.frame_step
                
                # Update render resolution from rig settings
                scene.render.resolution_x = item.render_resolution[0]
                scene.render.resolution_y = item.render_resolution[1]


@bpy.app.handlers.persistent
def update_collection_num_cameras(scene):
    """
    executed when appending or removing items from the rig_collection
    """

    for i, item in enumerate(scene.rig_collection):
        # Default to zero if collection is missing
        if not item.collection or item.collection.name not in bpy.data.collections:
            item.num_cameras = 0
            item.num_inkl_cameras = 0
            continue

        coll = item.collection
        cams = [obj for obj in coll.objects if obj.type == 'CAMERA']
        item.num_cameras = len(cams)

        # Cameras included for export/render are those not hidden in render
        included_cams = [cam for cam in cams if not getattr(cam, 'hide_render', False)]
        item.num_inkl_cameras = len(included_cams)

@bpy.app.handlers.persistent
def selected_camera_to_active(scene):
    if scene.sel_cam_active and bpy.context.object is not None and bpy.context.object.type == 'CAMERA':
        scene.camera = bpy.context.object

@bpy.app.handlers.persistent
def rebuild_world_materials_on_load(dummy):
    """Rebuild all world materials when file is loaded to ensure textures are properly reloaded."""
    try:
        scene = bpy.context.scene
        if hasattr(scene, 'rig_collection'):
            for item in scene.rig_collection:
                if item.source_filepath and item.source_filepath.strip():
                    create_or_update_world_material(item)
            print(f"Rebuilt {len(scene.rig_collection)} world materials on file load")
    except Exception as e:
        print(f"Error rebuilding world materials on load: {e}")
    


###########################################################################
### Operators #############################################################
###########################################################################

class RIG_OT_create_perspective_camera(bpy.types.Operator):
    """Create a perspective camera for the selected rig"""
    bl_idname = 'object.rig_create_perspective_camera'
    bl_label = 'Create Perspective Camera'
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        idx = scene.rig_index
        
        if 0 <= idx < len(scene.rig_collection):
            item = scene.rig_collection[idx]
            
            if item.rig_type != 'PERSPECTIVE':
                self.report({'WARNING'}, 'Can only create camera for Perspective rigs')
                return {'CANCELLED'}
            
            cam_obj = create_perspective_camera(item, context)
            self.report({'INFO'}, f'Created camera: {cam_obj.name}')
        
        return {'FINISHED'}


class RIG_OT_browse_media(bpy.types.Operator):
    """Browse for media file (movie or image sequence)"""
    bl_idname = 'object.rig_browse_media'
    bl_label = 'Browse Media'
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(
        name="File Path",
        subtype='FILE_PATH'
    )
    
    filter_movie: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_image: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    
    def invoke(self, context, event):
        scene = context.scene
        
        # Set starting directory to blend file location or home
        if bpy.data.filepath:
            # Use the directory of the blend file, add trailing slash to stay in directory
            blend_dir = os.path.dirname(bpy.data.filepath)
            self.filepath = os.path.join(blend_dir, '')
        else:
            self.filepath = os.path.expanduser('~')
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        scene = context.scene
        idx = scene.rig_index
        
        if 0 <= idx < len(scene.rig_collection):
            item = scene.rig_collection[idx]
            item.source_filepath = self.filepath
        
        return {'FINISHED'}


class RIG_OT_actions(bpy.types.Operator):
    '''Move rig items up and down, add and remove'''
    bl_idname = 'object.rig_action'
    bl_label = 'RIG Actions'
    bl_description = 'Add, remove & reorder rigs'
    bl_options = {'REGISTER'}

    action: bpy.props.EnumProperty(
        items=(
            ('UP', 'Move Up', ''),
            ('DOWN', 'Move Down', ''),
            ('REMOVE', 'Remove Rig', ''),
            ('ADD', 'Add Rig', '')))

    def invoke(self, context, event):
        scn = context.scene
        idx = scn.rig_index

        try:
            item = scn.rig_collection[idx]
        except IndexError:
            pass
        else:
            if self.action == 'DOWN' and idx < len(scn.rig_collection) - 1:
                item_next = scn.rig_collection[idx+1].name
                scn.rig_collection.move(idx, idx+1)
                scn.rig_index += 1
                info = 'Item {:s} moved to position {:d}'.format(item.name, scn.rig_index + 1)
                self.report({'INFO'}, info)

            elif self.action == 'UP' and idx >= 1:
                item_prev = scn.rig_collection[idx-1].name
                scn.rig_collection.move(idx, idx-1)
                scn.rig_index -= 1
                info = 'Item {:s} moved to position {:d}'.format(item.name, scn.rig_index + 1)
                self.report({'INFO'}, info)

            elif self.action == 'REMOVE':
                info = 'Item {:s} removed from list'.format(scn.rig_collection[idx].name)
                # Remove the managed collection and world material before removing the item
                remove_rig_collection(item)
                remove_world_material(item)
                scn.rig_collection.remove(idx)
                # Keep index valid: if we removed the last item, select the new last item
                if idx >= len(scn.rig_collection) and len(scn.rig_collection) > 0:
                    scn.rig_index = len(scn.rig_collection) - 1
                else:
                    scn.rig_index = max(0, idx)
                self.report({'INFO'}, info)

        if self.action == 'ADD':
            item = scn.rig_collection.add()
            item.ID = scn.max_rig_ID
            item.name = 'Rig_{:d}'.format(scn.max_rig_ID)
            scn.rig_index = len(scn.rig_collection)-1

            # Initialize resolution to 2K default
            item.render_resolution = (2048, 1080)

            # Leave source_filepath empty initially
            # The file browser will set the default path when opened
            item.source_filepath = ''

            # Create the managed collection for this rig
            create_rig_collection(item)
            
            # Create world material for this rig
            create_or_update_world_material(item)

            scn.max_rig_ID += 1

            info = '{:s} added to list'.format(item.name)
            self.report({'INFO'}, info)
        
        return {'FINISHED'}

###########################################################################
### UI ####################################################################
###########################################################################

class RIG_UL_LIST(bpy.types.UIList):
    '''
    RIG_LIST - Multi-column layout with inline boolean toggles
    '''

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Multi-column layout
            row = layout.row(align=True)
            
            row.prop(item, 'name', text='', emboss=False)

            row.label(text=f"{item.num_inkl_cameras}/{item.num_cameras}", icon='CAMERA_DATA')
            row.label(text=f"{projected_frames_for_rig(item)}", icon='RESTRICT_RENDER_OFF')

            row.prop(item, 'include_in_json', text='', icon='COPYDOWN' if item.include_in_json else 'X', emboss=True)
            row.prop(item, 'do_render', text='', icon='RESTRICT_RENDER_OFF' if item.do_render else 'RESTRICT_RENDER_ON', emboss=True)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text='', icon='CAMERA_DATA')

    def invoke(self, context, event):
        pass


class UIListPanelRigCollection(bpy.types.Panel):
    '''Creates a Panel in the Object properties window'''
    bl_idname = 'COLMAP_RIG_COLLECTION_PT_panel'
    bl_label = 'Rig Manager'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'COLMAP Rig'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        
        ######## Rig Collection List ########
        rows = 2
        row = layout.row()
        row.template_list('RIG_UL_LIST', 'a list', scene, 'rig_collection', scene, 'rig_index', rows=rows)

        col = row.column(align=True)
        col.operator('object.rig_action', icon='EVENT_PLUS', text='').action = 'ADD'
        col.operator('object.rig_action', icon='EVENT_MINUS', text='').action = 'REMOVE'
        col.separator()
        col.operator('object.rig_action', icon='EVENT_UP_ARROW', text='').action = 'UP'
        col.operator('object.rig_action', icon='EVENT_DOWN_ARROW', text='').action = 'DOWN'
        #####################################
        row = layout.row()
        row.prop(scene, 'sel_cam_active', text='Auto-activate selected camera')

        # Total across rigs with do_render=True
        total = 0
        try:
            total = sum(projected_frames_for_rig(i) for i in scene.rig_collection if getattr(i, 'do_render', False))
        except Exception:
            total = 0
        # layout.separator()
        total_row = layout.row()
        total_row.label(text=f"Total projected frames (queued): {total}", icon='SEQUENCE')

        layout.separator()
        row = layout.row()
        row.label(text='Rig Settings:')
        row = layout.row()
        # show editable fields for the currently selected rig item
        idx = scene.rig_index if hasattr(scene, 'rig_index') else 0

        if len(scene.rig_collection) > 0 and 0 <= idx < len(scene.rig_collection):
            item = scene.rig_collection[idx]
            box = layout.box()
            
            # Title row with centered, scaled text
            title_row = box.row()
            title_row.alignment = 'CENTER'
            title_row.scale_y = 1.2
            title_row.label(text=f'Selected: {item.name}')
            
            # Info grid - 2x2 layout with consistent spacing
            grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
            grid.label(text='Type: {:s}'.format(item.source_type), icon='FILE_MOVIE')
            grid.label(text='Cameras: {:d}'.format(item.num_cameras), icon='CAMERA_DATA')
            grid.label(text='Frames: {:d}'.format(item.media_frame_count), icon='MOD_TIME')
            
            # Projected frames for this rig (independent of do_render)
            proj_frames = projected_frames_for_rig(item)
            grid.label(text=f"Render: {proj_frames}", icon='RENDER_ANIMATION')

            box.prop(item, 'name')
            
            # Rig type selector
            box.prop(item, 'rig_type', text='Type')
            
            # Media section
            media_box = box.box()
            media_box.label(text='Media', icon='FILE_FOLDER')
            rowm = media_box.row(align=True)
            rowm.prop(item, 'source_filepath', text='Path')
            rowm.operator('object.rig_browse_media', text='', icon='FILEBROWSER')
            rowm = media_box.row(align=True)
            rowm.label(text=f'Auto: {item.media_frame_count}', icon='TIME')
            
            # For perspective rigs, show camera creation button if no camera exists
            if item.rig_type == 'PERSPECTIVE' and item.collection:
                cams = [obj for obj in item.collection.objects if obj.type == 'CAMERA']
                if not cams:
                    row = box.row()
                    row.operator('object.rig_create_perspective_camera', text='Create Camera', icon='CAMERA_DATA')
            
            # Resolution section
            res_box = box.box()
            res_box.label(text='Resolution', icon='IMAGE_DATA')
            split = res_box.split(factor=0.45, align=True)
            split.label(text='Render Resolution:')
            col_res = split.column(align=True)
            col_res.enabled = (item.rig_type == 'EQUIRECT_360')
            col_res.prop(item, 'render_resolution', index=0, text='X')
            col_res.prop(item, 'render_resolution', index=1, text='Y')
            
            # Frames section
            frames_box = box.box()
            frames_box.label(text='Frames', icon='SEQUENCE')
            rowf = frames_box.row(align=True)
            rowf.prop(item, 'start_frame', text='Start')
            rowf.prop(item, 'end_frame', text='End')
            rowf.prop(item, 'frame_step', text='Step')

            # Flags section
            flags_box = box.box()
            flags_box.label(text='Flags', icon='SETTINGS')
            flags_grid = flags_box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
            flags_grid.prop(item, 'include_in_json')
            flags_grid.prop(item, 'do_render')
            exif_cell = flags_grid.column()
            exif_cell.enabled = (item.rig_type == 'EQUIRECT_360')
            exif_cell.prop(item, 'write_exif')
            comp_cell = flags_grid.column()
            comp_cell.enabled = (item.rig_type == 'PERSPECTIVE')
            comp_cell.prop(item, 'use_compositor_media')


        else:
            layout.label(text='No rigs in list')

###########################################################################
### Register Modules ######################################################
###########################################################################

classes = (
    RigItem,
    RIG_UL_LIST,
    UIListPanelRigCollection,
    RIG_OT_create_perspective_camera,
    RIG_OT_browse_media,
    RIG_OT_actions,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.rig_collection = bpy.props.CollectionProperty(type=RigItem)
    bpy.types.Scene.rig_index = bpy.props.IntProperty(
        name='Rig Index', 
        default=0,
        update=lambda self, context: update_collection_visibility(context.scene)
    )
    bpy.types.Scene.max_rig_ID = bpy.props.IntProperty(name='max. Rig ID', default=0)
    bpy.types.Scene.sel_cam_active = bpy.props.BoolProperty(
        name='Auto-activate Selected Camera',
        description='Automatically set the selected camera as the active scene camera',
        default=True
    )

    bpy.app.handlers.depsgraph_update_post.append(update_collection_num_cameras)
    bpy.app.handlers.depsgraph_update_post.append(selected_camera_to_active)
    bpy.app.handlers.load_post.append(rebuild_world_materials_on_load)
    
    # Do not create/link collections during register; context may be restricted.
    # Parent collection will be ensured lazily when creating a rig item.

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.rig_collection
    del bpy.types.Scene.rig_index
    del bpy.types.Scene.max_rig_ID
    del bpy.types.Scene.sel_cam_active

    bpy.app.handlers.depsgraph_update_post.remove(update_collection_num_cameras)
    bpy.app.handlers.depsgraph_update_post.remove(selected_camera_to_active)
    bpy.app.handlers.load_post.remove(rebuild_world_materials_on_load)