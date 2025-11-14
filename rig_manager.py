#rig_manager.py
import bpy
import os


# Rig Item Property Group
class RigItem(bpy.types.PropertyGroup):
    ID: bpy.props.IntProperty(
        name = 'ID',
        default = 0
        )
    name: bpy.props.StringProperty(
    name = 'Rig Name',
    default = 'Rig ###'
    )
    # Pointer to the managed collection in the scene
    collection: bpy.props.PointerProperty(
        name = 'Rig Collection',
        type = bpy.types.Collection,
        description = 'The Blender collection managed by this rig item'
    )
    # Path to movie clip or image sequence
    source_filepath: bpy.props.StringProperty(
        name = 'Source Path',
        subtype = 'FILE_PATH', # Gives it a file browser icon in the UI
        description = 'Path to the Movie Clip or Image Sequence',
        default = ''
    )
    # Type of source selected
    source_type: bpy.props.EnumProperty(
        name = 'Source Type',
        items = [
            ('MOVIE_CLIP', 'Movie Clip', 'A single movie file'),
            ('IMAGE_SEQUENCE', 'Image Sequence', 'A sequence of image files (e.g., EXR, PNG)'),
            ('DUMMY_RIG', 'Dummy Rig', 'A placeholder rig without media'),
        ],
        description='Type of media being used'
    )
    media_frame_count: bpy.props.IntProperty(
        name = 'Media Frame Count',
        default = 100,
        min = 1
    )
    # Rendering parameters
    start_frame: bpy.props.IntProperty(
        name = 'Start Frame',
        default = 1,
        min = 1
    )
    end_frame: bpy.props.IntProperty(
        name = 'End Frame',
        default = 250,
        min = 1
    )
    frame_step: bpy.props.IntProperty(
        name = 'Frame Step',
        default = 10,
        min = 1
    )


###########################################################################
### Helper Functions #####################################################
###########################################################################

def ensure_rig_config_collection():
    """Ensure the 'rig_config' parent collection exists and is linked to the scene."""
    parent_name = 'rig_config'
    if parent_name in bpy.data.collections:
        parent_coll = bpy.data.collections[parent_name]
    else:
        parent_coll = bpy.data.collections.new(parent_name)
        bpy.context.scene.collection.children.link(parent_coll)
    return parent_coll

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
        # Unlink from all parents and remove
        for parent in coll.users_scene:
            parent.collection.children.unlink(coll)
        # Also unlink from rig_config if present
        if 'rig_config' in bpy.data.collections:
            parent_coll = bpy.data.collections['rig_config']
            if coll.name in parent_coll.children:
                parent_coll.children.unlink(coll)
        # Remove the collection data
        bpy.data.collections.remove(coll)
        rig_item.collection = None

def sync_collection_name(rig_item):
    """Sync the collection name with the rig_item name (called when user changes name)."""
    if rig_item.collection and rig_item.collection.name != rig_item.name:
        rig_item.collection.name = rig_item.name

###########################################################################
### Operators #############################################################
###########################################################################

class RIG_OT_actions(bpy.types.Operator):
    '''Move rig items up and down, add and remove'''
    bl_idname = 'object.rig_action'
    bl_label = 'RIG Actions'
    bl_description = 'Move rig items up and down, add and remove'
    bl_options = {'REGISTER'}

    action: bpy.props.EnumProperty(
        items=(
            ('UP', 'Up', ''),
            ('DOWN', 'Down', ''),
            ('REMOVE', 'Remove', ''),
            ('ADD', 'Add', '')))

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
                # Remove the managed collection before removing the item
                remove_rig_collection(item)
                scn.rig_index -= 1
                scn.rig_collection.remove(idx)
                self.report({'INFO'}, info)

        if self.action == 'ADD':
            item = scn.rig_collection.add()
            # item.obj_type = context.object.type
            item.ID = scn.max_rig_ID
            item.name = 'Rig_{:d}'.format(scn.max_rig_ID)
            scn.rig_index = len(scn.rig_collection)-1

            # Default source filepath: folder of current .blend if saved,
            # otherwise default to the user's home directory.
            if bpy.data.filepath:
                item.source_filepath = os.path.dirname(bpy.data.filepath)
            else:
                item.source_filepath = os.path.expanduser('~')

            # Create the managed collection for this rig
            create_rig_collection(item)

            scn.max_rig_ID += 1

            info = '{:s} added to list'.format(item.name)
            self.report({'INFO'}, info)
        
        return {'FINISHED'}

###########################################################################
### UI ####################################################################
###########################################################################

class RIG_UL_LIST(bpy.types.UIList):
    '''
    RIG_LIST
    '''

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        # Set Icon
        custom_icon = 'COLLECTION_COLOR_02'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=f'ID{item.ID:2d} | {item.name}', icon = custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text='', icon = custom_icon)

    def invoke(self, context, event):
        pass

class UIListPanelRigCollection(bpy.types.Panel):
    '''Creates a Panel in the Object properties window'''
    bl_idname = 'COLMAP_RIG_COLLECTION_PT_panel'
    bl_label = 'COLMAP Rig Exporter'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'COLMAP Rig Exp.'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object

        row = layout.row()
        row.label(text='test 1')

        ##########
        rows = 2
        row = layout.row()
        # row.template_list('CUSTOM_UL_items', '', scn, 'custom', scn, 'rig_index', rows=rows)
        row.template_list('RIG_UL_LIST', 'a list', scene, 'rig_collection', scene, 'rig_index', rows=rows)

        col = row.column(align=True)
        col.operator('object.rig_action', icon='ZOOM_IN', text='').action = 'ADD'
        col.operator('object.rig_action', icon='ZOOM_OUT', text='').action = 'REMOVE'
        col.separator()
        col.operator('object.rig_action', icon='TRIA_UP', text='').action = 'UP'
        col.operator('object.rig_action', icon='TRIA_DOWN', text='').action = 'DOWN'
        #######

        
        row = layout.row()
        row.label(text='Rig Settings:')
        row = layout.row()
        # show editable fields for the currently selected rig item
        idx = scene.rig_index if hasattr(scene, 'rig_index') else 0
        if len(scene.rig_collection) > 0 and 0 <= idx < len(scene.rig_collection):
            item = scene.rig_collection[idx]
            box = layout.box()
            box.label(text=f'Selected: {item.name}')
            box.prop(item, 'name')
            box.prop(item, 'source_type')
            box.prop(item, 'source_filepath')
            box.prop(item, 'media_frame_count')
            row = box.row()
            row.prop(item, 'start_frame')
            row.prop(item, 'end_frame')
            box.prop(item, 'frame_step')
        else:
            layout.label(text='No rigs in list')

###########################################################################
### Collection Protection (Depsgraph Handler) ############################
###########################################################################

@bpy.app.handlers.persistent
def protect_managed_collections(scene, depsgraph):
    """Revert any user changes to managed collections (name, visibility, parent)."""
    # Check if rig_config exists
    if 'rig_config' not in bpy.data.collections:
        return
    
    parent_coll = bpy.data.collections['rig_config']
    
    # Iterate through all rig items and ensure their collections are protected
    for item in scene.rig_collection:
        if item.collection:
            coll = item.collection
            # Sync name if user changed it
            if coll.name != item.name:
                coll.name = item.name
            # Note: Blender doesn't allow preventing collection renames/moves via API alone.
            # A more robust solution would use msgbus subscriptions or check on every depsgraph update.
            # For now, we sync the name back on depsgraph updates.

###########################################################################
### Register Modules ######################################################
###########################################################################

classes = (
    RigItem,
    RIG_UL_LIST,
    UIListPanelRigCollection,
    RIG_OT_actions,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.rig_collection = bpy.props.CollectionProperty(type=RigItem)
    bpy.types.Scene.rig_index = bpy.props.IntProperty(name='Rig Index', default=0)
    bpy.types.Scene.max_rig_ID = bpy.props.IntProperty(name='max. Rig ID', default=0)
    
    # Register depsgraph handler to protect managed collections
    if protect_managed_collections not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(protect_managed_collections)
    
    # Ensure rig_config collection exists on register
    ensure_rig_config_collection()

def unregister():
    # Remove depsgraph handler
    if protect_managed_collections in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(protect_managed_collections)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.rig_collection
    del bpy.types.Scene.rig_index
    del bpy.types.Scene.max_rig_ID