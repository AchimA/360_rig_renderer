#rig_manager.py
import bpy






###########################################################################
######################### Register Modules ################################
###########################################################################


classes = (
    COLMAP_RIG_OT_export,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)