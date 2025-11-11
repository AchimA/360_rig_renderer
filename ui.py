# ui.py
import bpy

class COLMAP_RIG_PT_panel(bpy.types.Panel):
    bl_idname = "COLMAP_RIG_PT_panel"
    bl_label = "COLMAP Rig Exporter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'COLMAP Rig Exp.'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # scene properties (registered in __init__.py)
        if hasattr(scene, 'colmap_rig_output_path'):
            layout.prop(scene, 'colmap_rig_output_path')
        if hasattr(scene, 'colmap_rig_image_format'):
            layout.prop(scene, 'colmap_rig_image_format')
        if hasattr(scene, 'colmap_rig_zero_pad'):
            layout.prop(scene, 'colmap_rig_zero_pad')

        row = layout.row()
        row.operator('colmap_rig.export', text='Export rig JSON')
        row = layout.row()
        row.operator('colmap_rig.render', text='Render all rigs')
        # row.enabled = False


classes = (
    COLMAP_RIG_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
