# ui.py
import bpy

class COLMAP_RIG_PT_panel(bpy.types.Panel):
    bl_idname = 'COLMAP_RIG_PT_panel'
    bl_label = 'COLMAP Rig Exporter'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'COLMAP Rig'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.label(text='Cameras that are \'Disabled in Renders\' will be skipped.', icon='RESTRICT_RENDER_ON')
        row = layout.row()
        row.operator(
            'colmap_rig.export',
            text='Export rig JSON',
            icon='OUTLINER'
             )
        row = layout.row()
        row.operator(
            'colmap_rig.render',
            text='Render all rigs',
            icon='SCENE',
            )
        # row.enabled = False


classes = (
    COLMAP_RIG_PT_panel,
)

###########################################################################
######################### Register Modules ################################
###########################################################################

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
