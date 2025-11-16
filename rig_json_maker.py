import bpy
import os
import json
import mathutils
from bpy.types import Operator
from bpy.props import StringProperty


def _get_evaluated_matrix(obj, depsgraph):
    '''Return the evaluated world matrix for an object using the depsgraph.'''
    obj_eval = obj.evaluated_get(depsgraph)
    # ensure we return a copy to avoid mutating Blender's internal data
    return obj_eval.matrix_world.copy()


## Note: Previous coordinate-system conversion helper removed.
## Relative transforms are currently exported directly in Blender's frame
## using M_ref.inverted() @ M_cam. If axis flipping (Y/Z) is needed for
## COLMAP interpretation, apply it to the relative transform before
## extracting quaternion/translation.


class COLMAP_RIG_OT_export(Operator):
    bl_idname = 'colmap_rig.export'
    bl_label = 'Export rig JSON for COLMAP'
    bl_description = 'Export rigs (collections) as COLMAP rig JSON'

# --- 1. Define properties for the FileBrowser ---
    # The filepath property is what the file browser uses to return the selected path
    filepath: bpy.props.StringProperty(
        name='File Path',
        description='Folder to write rig_config.json',
        subtype='FILE_PATH',
    )

    # This is a dummy property to correctly open the file browser
    # The name is important: 'files', 'file_name', etc.
    # The file browser will automatically use this to set the default file name.
    filename: bpy.props.StringProperty(
        name='File Name',
        description='*.json file name',
        default='export.json', # --- 3. Default file name
        maxlen=1024,
    )

    # --- 3. Filter for .json files
    filter_glob: bpy.props.StringProperty(
        default='*.json', # Always enforce .txt extension
        options={'HIDDEN'},
        maxlen=255,
    )


    def invoke(self, context, event):
        # Set the initial directory for the file browser
        if bpy.data.filepath:
            # Start in blend file directory with default filename
            blend_dir = os.path.dirname(bpy.data.filepath)
            self.filepath = os.path.join(blend_dir, 'rig_config.json')
        else:
            # If not saved, start in user's home directory
            self.filepath = os.path.join(os.path.expanduser('~'), 'rig_config.json')

        # Open the file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        # self.filepath now contains the full path to the selected JSON file
        json_path = bpy.path.abspath(self.filepath)
        
        # Ensure the directory exists
        out_dir = os.path.dirname(json_path)
        os.makedirs(out_dir, exist_ok=True)
        
        rigs = []
        depsgraph = context.evaluated_depsgraph_get()

        # Iterate through rig items instead of all collections
        if not hasattr(scene, 'rig_collection'):
            self.report({'WARNING'}, 'No rig collection found in scene')
            return {'CANCELLED'}

        for rig_item in scene.rig_collection:
            # Skip rigs not marked for json export
            if not rig_item.include_in_json:
                continue

            # Skip if collection doesn't exist
            if not rig_item.collection or rig_item.collection.name not in bpy.data.collections:
                continue

            coll = rig_item.collection

            # Collect visible cameras in this collection
            # Only include cameras that are visible in both render and viewport
            cams = [
                obj
                for obj in coll.objects
                if obj.type == 'CAMERA' and not obj.hide_render
            ]

            if not cams:
                continue

            # Choose reference camera (first visible). User can modify later if needed.
            ref_cam = cams[0]
            M_ref = _get_evaluated_matrix(ref_cam, depsgraph)

            rig_entry = {'cameras': []}

            for cam in cams:
                M_cam = _get_evaluated_matrix(cam, depsgraph)

                if cam == ref_cam:
                    cam_entry = {
                        'image_prefix': f'{rig_item.name}/{cam.name}/',
                        'ref_sensor': True
                    }
                else:
                    # Compute relative transformation: from reference to this camera
                    # Extract clean rotation/translation to avoid scale/shear artifacts
                    R_ref = M_ref.to_quaternion().to_matrix().to_4x4()
                    R_ref.translation = M_ref.translation
                    
                    R_cam = M_cam.to_quaternion().to_matrix().to_4x4()
                    R_cam.translation = M_cam.translation
                    
                    T_cam_ref = R_ref.inverted() @ R_cam
                    
                    # Extract quaternion and translation
                    q = T_cam_ref.to_quaternion()
                    t = T_cam_ref.to_translation()
                    cam_entry = {
                        'image_prefix': f'{rig_item.name}/{cam.name}/',
                        'cam_from_rig_rotation': [q.w, q.x, q.y, q.z],
                        'cam_from_rig_translation': [t.x, t.y, t.z]
                    }

                rig_entry['cameras'].append(cam_entry)

            rigs.append(rig_entry)


        # Write JSON file to selected path
        with open(json_path, 'w') as f:
            json.dump(rigs, f, indent=4)

        self.report({'INFO'}, f'Exported {len(rigs)} rigs to {json_path}')
        return {'FINISHED'}

    

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