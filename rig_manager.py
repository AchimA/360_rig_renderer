#rig_manager.py
import bpy



# Rig Item Property Group
class RigItem(bpy.types.PropertyGroup):
    ID: bpy.props.IntProperty(
        name='ID',
        default=0
        )
    name: bpy.props.StringProperty(
    name='Rig Name',
    default='Rig ###'
    )
    
    # Path to movie clip or image sequence
    source_filepath: bpy.props.StringProperty(
        name="Source Path",
        subtype='FILE_PATH', # Gives it a file browser icon in the UI
        description="Path to the Movie Clip or Image Sequence"
    )
    
    # Type of source selected
    source_type: bpy.props.EnumProperty(
        name="Source Type",
        items=[
            ('MOVIE_CLIP', "Movie Clip", "A single movie file"),
            ('IMAGE_SEQUENCE', "Image Sequence", "A sequence of image files (e.g., EXR, PNG)"),
            ('DUMMY_RIG', "Dummy Rig", "A placeholder rig without media"),
        ],
        description="Type of media being used"
    )
    media_frame_count: bpy.props.IntProperty(
        name="Media Frame Count",
        default=100,
        min=1
    )

    # Rendering parameters
    start_frame: bpy.props.IntProperty(
        name="Start Frame",
        default=1,
        min=1
    )
    end_frame: bpy.props.IntProperty(
        name="End Frame",
        default=250,
        min=1
    )
    frame_step: bpy.props.IntProperty(
        name="Frame Step",
        default=10,
        min=1
    )


class RIG_UL_LIST(bpy.types.UIList):
    """
    RIG_LIST
    """

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        # Set Icon
        custom_icon = 'COLLECTION_COLOR_02'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=f'{item.ID:2d} {item.name}', icon = custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon = custom_icon)


class UIListPanelRigCollection(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_idname = "COLMAP_RIG_COLLECTION_PT_panel"
    bl_label = "COLMAP Rig Exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'COLMAP Rig Exp.'
    bl_context = 'objectmode'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object

        row = layout.row()
        row.label(text='test 1')

        row = layout.row()
        row.operator(
            'object.new_rig',
            text='New Rig',
            icon='FILE_REFRESH'
            )
        
        layout.template_list('RIG_UL_LIST', 'a list', scene, 'rig_collection', scene, 'rig_index')
        
        row = layout.row()
        row.label(text='Rig Settings:')
        row = layout.row()


class NewRig(bpy.types.Operator):
    bl_idname = "object.new_rig"
    bl_label = "Add a new rig"

    def execute(self, context):
        context.scene.rig_collection.add()

        return {'FINISHED'}

###########################################################################
######################### Register Modules ################################
###########################################################################


classes = (
    RigItem,
    RIG_UL_LIST,
    UIListPanelRigCollection,
    NewRig,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.rig_collection = bpy.props.CollectionProperty(type=RigItem)
    bpy.types.Scene.rig_index = bpy.props.IntProperty(name='Rig Index', default=0)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.rig_collection
    del bpy.types.Scene.rig_index